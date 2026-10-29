import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdirSync, writeFileSync, readFileSync, rmSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'
import { readStore, saveStore, defaults, cropPixels } from '../dist/profiles.js'

const scratch = process.env.WEBCAMTUNER_TEST_ROOT
if (!scratch) throw new Error('Set WEBCAMTUNER_TEST_ROOT to a disposable test directory')
function fixture(t) {
  const directory = join(scratch, randomUUID())
  mkdirSync(directory, { recursive: true })
  t.after(() => rmSync(directory, { recursive: true, force: true }))
  return join(directory, 'profiles.json')
}
test('crop and background choices survive a new read with private file permissions', t => {
  const path = fixture(t), store = defaults()
  store.profiles[0].crop = { zoom: 2, centerX: 0.6, centerY: 0.4 }
  store.profiles[0].background = { mode: 'blur', imagePath: '' }
  const saved = saveStore(store, path)
  assert.equal(saved.revision, 1)
  assert.deepEqual(readStore(path), saved)
  assert.equal(statSync(path).mode & 0o777, 0o600)
})
test('an old panel cannot overwrite a newer profile', t => {
  const path = fixture(t), original = defaults()
  saveStore(original, path)
  const before = readFileSync(path, 'utf8')
  assert.throws(() => saveStore(original, path), /another panel/)
  assert.equal(readFileSync(path, 'utf8'), before)
})
test('old profiles adopt mirror and autostart defaults; explicit disabled settings survive reload', t => {
  const path = fixture(t), old = defaults()
  delete old.profiles[0].mirror
  delete old.profiles[0].autostartCamera
  delete old.lastCamera
  writeFileSync(path, JSON.stringify(old))
  const migrated = readStore(path)
  assert.equal(migrated.profiles[0].mirror, true)
  assert.equal(migrated.profiles[0].autostartCamera, true)
  assert.equal(migrated.lastCamera, '')
  migrated.profiles[0].mirror = false
  migrated.profiles[0].autostartCamera = false
  saveStore(migrated, path)
  assert.equal(readStore(path).profiles[0].mirror, false)
  assert.equal(readStore(path).profiles[0].autostartCamera, false)
})
test('invalid framing and duplicate IDs are rejected before writes', t => {
  const path = fixture(t), bad = defaults()
  bad.profiles[0].crop = { zoom: 2, centerX: 0, centerY: 0.5 }
  assert.throws(() => saveStore(bad, path))
  const duplicate = defaults()
  duplicate.profiles.push(structuredClone(duplicate.profiles[0]))
  assert.throws(() => saveStore(duplicate, path))
})
test('corrupt and unsupported stores are preserved rather than silently reset', t => {
  const path = fixture(t)
  writeFileSync(path, '{broken')
  assert.throws(() => saveStore(defaults(), path))
  assert.equal(readFileSync(path, 'utf8'), '{broken')
  writeFileSync(path, JSON.stringify({ ...defaults(), schemaVersion: 2 }))
  assert.throws(() => readStore(path))
})
test('a second writer is refused without deleting its lock', t => {
  const path = fixture(t)
  writeFileSync(path + '.lock', 'other writer')
  assert.throws(() => saveStore(defaults(), path), /Another profile save/)
  assert.equal(readFileSync(path + '.lock', 'utf8'), 'other writer')
})
test('crop plan stays even and inside the frame at all edges', () => {
  for (const zoom of [1, 1.1, 2, 4]) {
    const edge = 0.5 / zoom
    for (const center of [edge, 0.5, 1 - edge]) {
      const crop = cropPixels({ zoom, centerX: center, centerY: center }, 1920, 1080)
      assert.equal(crop.x % 2, 0); assert.equal(crop.y % 2, 0)
      assert.equal(crop.width % 2, 0); assert.equal(crop.height % 2, 0)
      assert.ok(crop.x >= 0 && crop.x + crop.width <= 1920)
      assert.ok(crop.y >= 0 && crop.y + crop.height <= 1080)
    }
  }
  assert.deepEqual(cropPixels({ zoom: 2, centerX: 0.5, centerY: 0.5 }, 1920, 1080), { x: 480, y: 270, width: 960, height: 540 })
})
