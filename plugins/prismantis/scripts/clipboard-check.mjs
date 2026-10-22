import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { load } from './load.mjs'

if (process.platform !== 'darwin') {
  console.log('Skipped native clipboard bridge check: macOS required')
  process.exit(0)
}

const { MAC_TABLE_COPY } = await load()
const payload = {
  html: '<table><tr><th>Name</th></tr><tr><td>Żółć &amp; שלום</td></tr></table>',
  text: 'Name\nŻółć & שלום\t中文',
}
const bridge = `
ObjC.import('AppKit')
var received = $.NSMutableArray.alloc.init
var testPasteboard = {
  writeObjects: function(objects) {
    received.addObjectsFromArray(objects)
    if (Number(received.count) !== 1 || !received.objectAtIndex(0).isKindOfClass($.NSPasteboardItem)) throw new Error('Expected a native NSPasteboardItem')
    return true
  },
  stringForType: function(type) { return received.objectAtIndex(0).stringForType(type) }
}
`
const helper = MAC_TABLE_COPY.replace('$.NSPasteboard.generalPasteboard', 'testPasteboard')
assert.notEqual(helper, MAC_TABLE_COPY)
const result = spawnSync('/usr/bin/osascript', ['-l', 'JavaScript', '-e', bridge + helper], {
  input: JSON.stringify(payload), encoding: 'utf8', timeout: 5000,
})
assert.equal(result.status, 0, result.stderr || result.error?.message)
const broken = spawnSync('/usr/bin/osascript', ['-l', 'JavaScript', '-e', bridge + helper.replace('$.NSArray.arrayWithObject(item)', '[item]')], {
  input: JSON.stringify(payload), encoding: 'utf8', timeout: 5000,
})
assert.notEqual(broken.status, 0)
assert.match(broken.stderr, /Expected a native NSPasteboardItem/)
console.log('Native clipboard bridge preserves NSPasteboardItem and both Unicode formats; implicit JavaScript arrays are rejected')
