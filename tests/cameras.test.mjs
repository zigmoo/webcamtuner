import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdirSync, writeFileSync, symlinkSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { randomUUID } from 'node:crypto'
import vm from 'node:vm'
import { cameraAliases } from '../dist/cameras.js'

const choice = {}
vm.runInNewContext(readFileSync(new URL('../ui/CameraChoice.js', import.meta.url), 'utf8'), choice)
const inputs = [{ id: '/dev/video7' }, { id: '/dev/video0' }]
const aliases = [{ path: '/dev/video7', key: 'by-id:usb-camera-A-video-index0', primary: true },
  { path: '/dev/video0', key: 'by-id:usb-camera-B-video-index0', primary: true }]

test('one webcam is chosen without saved preferences', () => {
  assert.equal(choice.pick([inputs[0]], aliases, '', '', '', ''), '/dev/video7')
})
test('remembered identity wins over a stale video node after reboot', () => {
  assert.equal(choice.pick(inputs, aliases, aliases[0].key, '', '/dev/video0', '/dev/video0'), '/dev/video7')
})
test('an existing selection survives hotplug and missing preferences use the OS default', () => {
  assert.equal(choice.pick(inputs, aliases, aliases[0].key, '/dev/video0', '', ''), '/dev/video0')
  assert.equal(choice.pick(inputs, aliases, 'missing', '', '', '/dev/video7'), '/dev/video7')
  assert.equal(choice.pick(inputs, aliases, 'missing', '', '', 'missing'), '/dev/video7')
  assert.equal(choice.pick([], aliases, '', '', '', ''), '')
})
test('secondary IR endpoints do not turn one physical webcam into an ambiguous choice', () => {
  const endpoints = [{ id: '/dev/video2' }, { id: '/dev/video4' }]
  const ids = [{ path: '/dev/video2', key: 'by-id:brio-video-index0', primary: true },
    { path: '/dev/video4', key: 'by-id:brio-video-index2', primary: false }]
  const visible = choice.visibleInputs(endpoints, ids)
  assert.equal(visible.length, 1)
  assert.equal(visible[0].id, '/dev/video2')
})
test('USB identity discovery reads aliases without opening capture devices', t => {
  const directory = join(process.env.WEBCAMTUNER_TEST_ROOT, randomUUID())
  mkdirSync(directory, { recursive: true })
  t.after(() => rmSync(directory, { recursive: true, force: true }))
  const target = join(directory, 'video7')
  writeFileSync(target, '')
  const ids = join(directory, 'by-id')
  mkdirSync(ids)
  symlinkSync(target, join(ids, 'usb-camera-A-video-index0'))
  const result = cameraAliases(ids)
  assert.deepEqual(result, [{ path: target, key: 'by-id:usb-camera-A-video-index0', primary: true }])
})
