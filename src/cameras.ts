import { readdirSync, realpathSync } from 'node:fs'
import { join } from 'node:path'

export function cameraAliases(directory = '/dev/v4l/by-id') {
  let names: string[]
  try { names = readdirSync(directory).sort() }
  catch (error: any) { if (error.code === 'ENOENT') return []; throw error }
  const result: { path: string; key: string; primary: boolean }[] = []
  for (const name of names) {
    try {
      result.push({ path: realpathSync(join(directory, name)), key: 'by-id:' + name, primary: name.endsWith('-video-index0') })
    } catch (error: any) {
      if (error.code !== 'ENOENT') throw error
    }
  }
  return result
}
