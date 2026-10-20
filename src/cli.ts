import { Cli, z } from 'incur'
import { execFileSync } from 'node:child_process'
import { readStore, saveStore, storePath, cropPixels } from './profiles.js'

const cli = Cli.create('webcamtuner', { version: '0.2.0', description: 'WebcamTuner preview: persist camera framing and background profiles. No capture starts automatically.' })
cli.command('read', { description: 'Read profiles and their revision without starting capture', run: () => readStore() })
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
    return { profile, crop: cropPixels(profile.crop, c.options.width, c.options.height), output: 'not-implemented', backgrounds: 'local-preview' }
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
  run: () => ({ profiles: storePath(), cropPreview: true, profilePersistence: true, virtualCamera: false, backgroundProcessing: 'local-preview', previewDependencies: ['python3', 'OpenCV', 'NumPy', 'Pillow'], remoteDiscovery: 'optional webcam_tool adapter', remoteCapture: false }),
})
export default cli
cli.serve()
