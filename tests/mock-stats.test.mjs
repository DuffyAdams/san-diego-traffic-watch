import test from 'node:test';
import assert from 'node:assert/strict';
import { buildStats, seedIncidents, filterIncidents } from '../traffic-app/mocks/data.mjs';

const incidents = seedIncidents();
const reference = new Date(buildStats(incidents, new URLSearchParams()).generatedAt);

test('mock history is repeatable, spans over two years and keeps recent fixture IDs first', () => {
  assert.deepEqual(seedIncidents(), incidents);
  assert.equal(incidents[0].incident_no, 'A-1001');
  assert.ok(new Date(incidents.at(-1).timestamp) < new Date(reference.getFullYear() - 2, reference.getMonth(), 1, 1));
  assert.ok(incidents.every(incident => new Date(incident.timestamp) < reference));
  assert.ok(incidents.filter(incident => incident.incident_no.startsWith('H-')).every(incident => !incident.active));
  assert.equal(new Set(incidents.map(incident => incident.incident_no)).size, incidents.length);
});

for (const source of ['', 'CHP', 'SDPD', 'SDFD']) {
  for (const [period, length] of [['day', 24], ['week', 7], ['month', 30], ['year', 12]]) {
    test(`${source || 'All'} ${period} has real seeded comparison counts`, () => {
      const query = new URLSearchParams({ date_filter: period });
      if (source) query.set('source', source);
      const stats = buildStats(incidents, query);
      assert.equal(stats.hourlyData.length, length);
      assert.equal(stats.previousPeriodData.length, length);
      assert.ok(stats.previousPeriodData.some(value => value > 0));
      assert.ok(stats.previousPeriodData.every(value => Number.isInteger(value) && value >= 0));
      assert.notDeepEqual(stats.previousPeriodData, stats.hourlyData);
      if (period === 'day') assert.deepEqual(stats.previousPeriodData, stats.previousWeekHourlyData);
      const withoutHistory = incidents.filter(incident => !incident.incident_no.startsWith('H-'));
      assert.equal(buildStats(withoutHistory, query).previousPeriodData, null);
    });
  }
}

test('unknown sources have no invented history and historic feed pagination stays unique', () => {
  assert.equal(buildStats(incidents, new URLSearchParams('source=UNKNOWN')).previousPeriodData, null);
  const page = filterIncidents(incidents, new URLSearchParams('limit=30&source=CHP'));
  assert.equal(page.length, 30);
  const last = page.at(-1);
  const next = filterIncidents(incidents, new URLSearchParams({ limit: '30', source: 'CHP', cursor: `${last.timestamp}|${last.incident_no}` }));
  assert.ok(next.every(incident => !page.some(first => first.incident_no === incident.incident_no)));
});
