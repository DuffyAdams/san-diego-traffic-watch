import test from 'node:test';
import assert from 'node:assert/strict';
import { truncateDescription } from '../traffic-app/src/utils/helpers.js';
test('descriptions up to the 200-character expand threshold remain complete', () => {
  for (const length of [150, 151, 176, 199, 200]) {
    const text = 'Road blocked. '.repeat(20).slice(0, length);
    assert.equal(truncateDescription(text), text);
  }
  assert.notEqual(truncateDescription('Road blocked. '.repeat(30)), 'Road blocked. '.repeat(30));
});
