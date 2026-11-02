import { z } from 'incur'
import { mkdirSync, readFileSync, openSync, closeSync, writeFileSync, fsyncSync, renameSync, unlinkSync } from 'node:fs'
import { join } from 'node:path'
import { homedir } from 'node:os'
import { randomUUID } from 'node:crypto'

const unit = z.number().finite().min(0).max(1)
export const profileSchema = z.object({
  id: z.string().regex(/^[a-z0-9-]{1,64}$/),
  name: z.string().trim().min(1).max(80),
  source: z.object({
    kind: z.enum(['local', 'remote']),
    host: z.string().max(253),
    camera: z.string().max(512),
  }).strict(),
  crop: z.object({ zoom: z.number().finite().min(1).max(4), centerX: unit, centerY: unit }).strict()
    .refine(c => c.centerX >= 0.5 / c.zoom && c.centerX <= 1 - 0.5 / c.zoom
      && c.centerY >= 0.5 / c.zoom && c.centerY <= 1 - 0.5 / c.zoom, 'Crop must stay inside the source frame'),
  background: z.object({ mode: z.enum(['none', 'blur', 'image']), imagePath: z.string().max(4096),
    crop: z.object({ zoom: z.number().finite().min(1).max(4), centerX: unit, centerY: unit }).strict().optional(),
  }).strict(),
  mirror: z.boolean().default(true),
  autostartCamera: z.boolean().default(true),
  restoreOnStart: z.boolean(),
}).strict()
export const storeSchema = z.object({
  schemaVersion: z.literal(1),
  revision: z.number().int().nonnegative(),
  activeProfile: z.string(),
  lastCamera: z.string().max(512).default(''),
  profiles: z.array(profileSchema).min(1).max(30),
}).strict().refine(s => new Set(s.profiles.map(p => p.id)).size === s.profiles.length, 'Profile IDs must be unique')
  .refine(s => s.profiles.some(p => p.id === s.activeProfile), 'Active profile must exist')
export type ProfileStore = z.infer<typeof storeSchema>
export function storePath(): string {
  return join(process.env.WEBCAMTUNER_CONFIG_ROOT || join(process.env.XDG_CONFIG_HOME || join(homedir(), '.config'), 'webcamtuner'), 'profiles.json')
}
export function defaults(): ProfileStore {
  return { schemaVersion: 1, revision: 0, activeProfile: 'desk', lastCamera: '', profiles: [{
    id: 'desk', name: 'Desk', source: { kind: 'local', host: '', camera: '' },
    crop: { zoom: 1, centerX: 0.5, centerY: 0.5 },
    background: { mode: 'none', imagePath: '' }, mirror: true, autostartCamera: true, restoreOnStart: true,
  }] }
}
export function readStore(path = storePath()): ProfileStore {
  let raw: string
  try { raw = readFileSync(path, 'utf8') }
  catch (error: any) { if (error.code === 'ENOENT') return defaults(); throw error }
  if (Buffer.byteLength(raw) > 131072) throw new Error('Profile file exceeds the size limit')
  return storeSchema.parse(JSON.parse(raw))
}
export function saveStore(input: unknown, path = storePath()): ProfileStore {
  const proposed = storeSchema.parse(input)
  const directory = join(path, '..')
  mkdirSync(directory, { recursive: true, mode: 0o700 })
  const lock = path + '.lock'
  let descriptor: number
  try { descriptor = openSync(lock, 'wx', 0o600) }
  catch (error: any) {
    if (error.code === 'EEXIST') throw new Error('Another profile save is active; reload and retry. A stale profiles.json.lock may need inspection after a crash.')
    throw error
  }
  const temporary = path + '.' + randomUUID()
  try {
    if (readStore(path).revision !== proposed.revision) throw new Error('Profiles changed in another panel; reload before saving')
    const updated = { ...proposed, revision: proposed.revision + 1 }
    const fd = openSync(temporary, 'wx', 0o600)
    try { writeFileSync(fd, JSON.stringify(updated, null, 2) + '\n'); fsyncSync(fd) }
    finally { closeSync(fd) }
    renameSync(temporary, path)
    const dirFd = openSync(directory, 'r')
    try { fsyncSync(dirFd) } finally { closeSync(dirFd) }
    const actual = readStore(path)
    if (JSON.stringify(actual) !== JSON.stringify(updated)) throw new Error('Saved profile verification failed')
    return actual
  } finally {
    try { unlinkSync(temporary) } catch {}
    closeSync(descriptor)
    unlinkSync(lock)
  }
}
export function cropPixels(crop: { zoom: number; centerX: number; centerY: number }, width: number, height: number) {
  // Keep dimensions and offsets even so common YUV output formats remain valid.
  const even = (v: number) => Math.floor(v / 2) * 2
  const w = Math.max(2, even(width / crop.zoom)), h = Math.max(2, even(height / crop.zoom))
  return { x: even(Math.max(0, Math.min(width - w, crop.centerX * width - w / 2))),
    y: even(Math.max(0, Math.min(height - h, crop.centerY * height - h / 2))), width: w, height: h }
}
