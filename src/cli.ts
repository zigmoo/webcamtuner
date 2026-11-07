import { Cli, z } from 'incur'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { readStore, saveStore, storePath, cropPixels } from './profiles.js'
import { cameraAliases } from './cameras.js'

const cli = Cli.create('webcamtuner', { version: '0.9.5', description: 'WebcamTuner preview: persist camera framing and background profiles. Preview autostart is a saved profile choice.' })
cli.command('read', { description: 'Read profiles and their revision without starting capture', run: () => readStore() })
cli.command('devices', { description: 'Read stable local webcam identifiers without opening a camera', run: () => ({ aliases: cameraAliases() }) })
cli.command('save', {
  description: 'Validate, atomically save, and read back profiles; rejects concurrent edits',
  options: z.object({ document: z.string().max(131072).describe('Complete profile store JSON with expected revision') }),
  run: c => saveStore(JSON.parse(c.options.document)),
})
cli.command('plan', {
  description: 'Show the saved crop in source pixels; does not start a pipeline',
  options: z.object({ width: z.number().int().min(2).max(16384).default(1920), height: z.number().int().min(2).max(16384).default(1080) }),
  run: c => {
    const store = readStore(), profile = store.profiles.find(p => p.id === store.activeProfile)!
    return { profile, crop: cropPixels(profile.crop, c.options.width, c.options.height), output: 'user-session PipeWire publisher; explicit Start output', backgrounds: 'shared compositor' }
  },
})
function backgroundLibrary(action: string, paths?: string, crop?: string, selectedPath?: string) {
  const args = [fileURLToPath(new URL('../bin/background-library.py', import.meta.url)), action]
  if (paths) args.push(crop ? '--path' : '--paths', paths)
  if (crop) args.push('--crop', crop)
  if (selectedPath) args.push('--selected-path', selectedPath)
  return JSON.parse(execFileSync(fileURLToPath(new URL('../bin/preview-python', import.meta.url)), args, { encoding: 'utf8', timeout: 60000, maxBuffer: 1048576 }))
}
cli.command('backgrounds', {
  description: 'List managed backgrounds and their storage directory',
  options: z.object({ selectedPath: z.string().max(4096).optional() }),
  run: c => backgroundLibrary('list', undefined, undefined, c.options.selectedPath),
})
cli.command('add-backgrounds', {
  description: 'Validate and copy images into the user background library, then read them back',
  options: z.object({ paths: z.string().max(90000).describe('JSON array of absolute local paths or file URLs') }),
  run: c => backgroundLibrary('add', c.options.paths),
})
cli.command('background-crop', {
  description: 'Save and verify the framing remembered for a managed background image',
  options: z.object({ path: z.string().max(4096), crop: z.string().max(256) }),
  run: c => backgroundLibrary('crop', c.options.path, c.options.crop),
})
function backgroundAction(action: string, path: string, id: string, extra: string[] = []) {
  return JSON.parse(execFileSync(fileURLToPath(new URL('../bin/preview-python', import.meta.url)), [fileURLToPath(new URL('../bin/background-library.py', import.meta.url)), action, '--path', path, '--id', id, ...extra], { encoding: 'utf8', timeout: 30000, maxBuffer: 1048576 }))
}
cli.command('lock-background', {
  description: 'Persist and verify a background lock',
  options: z.object({ path: z.string().max(4096), id: z.string().regex(/^[a-f0-9]{64}$/), locked: z.enum(['true', 'false']) }),
  run: c => backgroundAction('lock', c.options.path, c.options.id, ['--locked', String(c.options.locked)]),
})
cli.command('label-background', {
  description: 'Save an optional display label without renaming an image',
  options: z.object({ path: z.string().max(4096), id: z.string().regex(/^[a-f0-9]{64}$/), label: z.string().max(80) }),
  run: c => backgroundAction('label', c.options.path, c.options.id, ['--label', c.options.label]),
})
cli.command('background-overlay', {
  description: 'Save and verify per-image label visibility and opacity',
  options: z.object({ path: z.string().max(4096), id: z.string().regex(/^[a-f0-9]{64}$/), overlay: z.string().max(2048) }),
  run: c => backgroundAction('overlay', c.options.path, c.options.id, ['--overlay', c.options.overlay]),
})
cli.command('trash-background', {
  description: 'Move a background to OS Trash; update affected profiles and library metadata',
  options: z.object({ path: z.string().max(4096), id: z.string().regex(/^[a-f0-9]{64}$/) }),
  run: c => {
    const image = backgroundAction('inspect', c.options.path, c.options.id)
    if (image.locked) throw new Error('Unlock this background before moving it to Trash.')
    const before = readStore(), next = JSON.parse(JSON.stringify(before))
    const affected: string[] = []
    for (const profile of next.profiles) if (profile.background.mode === 'image' && profile.background.imagePath === c.options.path) {
      profile.background = { mode: 'blur', imagePath: '' }
      affected.push(profile.id)
    }
    const updated = affected.length ? saveStore(next) : before
    try {
      const keep = updated.profiles.filter(p => p.background.mode === 'image').map(p => p.background.imagePath)
      const result = backgroundAction('trash', c.options.path, c.options.id, ['--keep-paths', JSON.stringify(keep)])
      return { ...result, document: updated, trashedPath: c.options.path, replacedProfiles: affected }
    } catch (error) {
      if (affected.length) {
        try { saveStore({ ...before, revision: updated.revision }) } catch {}
      }
      return { ...backgroundLibrary('list'), document: readStore(), trashError: String(error), trashedPath: c.options.path, replacedProfiles: [] }
    }
  },
})
cli.command('remote', {
  description: 'Inspect hosts or devices through the existing webcam_tool; never starts a viewer or remote capture',
  options: z.object({ host: z.string().regex(/^[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}$/).optional() }),
  run: c => {
    const args = c.options.host ? ['devices', c.options.host, '--json'] : ['hosts', '--json']
    return JSON.parse(execFileSync('webcam_tool', args, { encoding: 'utf8', timeout: 30000, maxBuffer: 1048576 }))
  },
})
cli.command('doctor', {
  description: 'Report prototype capabilities and profile path',
  run: () => ({ profiles: storePath(), cropPreview: true, profilePersistence: true, virtualCamera: 'user-session PipeWire; optional user-only V4L2 adapter for native Zoom', backgroundProcessing: 'shared compositor with independent consumer readbacks in Test', appAcceptance: 'requires verification in each actual app', matting: 'RVM MobileNetV3 with recurrent states', capture: 'largest supported 16:9 mode up to UHD 4K', output: '1280x720; nominal 30 fps; actual fresh FPS measured separately', previewDependencies: ['User-local Python runtime prepared from Setup', 'OpenCV', 'NumPy', 'Pillow', 'ONNX Runtime 1.31.0'], remoteDiscovery: 'optional webcam_tool adapter', remoteCapture: false }),
})
cli.serve()
