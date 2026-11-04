const {test} = require('node:test');
const assert = require('node:assert/strict');
const {guides,explain} = require('./interpretation.js');
const observed = require('./data.json');
const now = Date.parse('2026-11-04T14:00:00Z');
function series(values, unit='%', frequency='monthly') {
  return {unit,frequency,as_of:'2026-09-01',fetch_status:'ok',points:values.map((value,i)=>({date:['2026-06-01','2026-09-01'][i],value}))};
}
test('all 30 observed indicators have explanations and education',()=>{
  assert.equal(Object.keys(guides).length,30);
  for(const [key,value] of Object.entries(observed.history)) {
    for(const days of [90,180,365]) {
      const reading=explain(key,value,days,now);
      assert.ok(reading.guide?.definition,key);
      assert.ok(reading.guide.watch && reading.guide.caution,key);
      assert.ok(reading.observation && reading.meaning,key);
      assert.doesNotMatch(reading.observation+reading.meaning,/undefined|NaN|Infinity/);
    }
  }
});
test('changes in percentage rates use percentage points',()=>{
  assert.match(explain('core_pce',series([3,4]),365,now).observation,/1 個百分點/);
  assert.doesNotMatch(explain('core_pce',series([3,4]),365,now).observation,/33/);
});
test('positive but slowing inflation is not described as falling prices',()=>{
  const reading=explain('core_pce',series([4,3]),365,now);
  assert.match(reading.meaning,/放緩/);assert.match(reading.meaning,/不代表物價下降/);
});
test('payroll comparisons describe monthly gains, never annual cumulative jobs',()=>{
  const reading=explain('nonfarm_payrolls',series([76,29],'千人'),365,now);
  assert.match(reading.observation,/單月新增工作/);
  assert.match(reading.meaning,/仍淨新增/);
});
test('negative NFCI can tighten while remaining looser than average',()=>{
  const reading=explain('nfci',series([-.6,-.4],'指數','weekly'),365,Date.parse('2026-09-05'));
  assert.match(reading.meaning,/較歷史平均寬鬆/);assert.match(reading.meaning,/較起點趨緊/);
});
test('stale or failed observations do not become current conclusions',()=>{
  const stale=explain('vix',series([20,25],'指數','daily'),365,now);
  assert.match(stale.observation,/資料可能過期/);
  assert.match(stale.meaning,/舊資料/);
  const failed=series([20,25],'指數','monthly');failed.fetch_status='failed';
  assert.match(explain('vix',failed,365,now).observation,/更新失敗/);
});
test('zero baseline never produces an infinite percentage change',()=>{
  const reading=explain('rrp',series([0,2],'十億美元'),365,now);
  assert.match(reading.observation,/無法計算百分比/);
});
test('insufficient observations do not generate a trend',()=>{
  assert.match(explain('vix',{points:[]},365,now).observation,/不足/);
});
test('Sahm threshold is a warning rule and not an official recession declaration',()=>{
  assert.match(explain('sahm_rule',series([.3,.5],'百分點'),365,now).meaning,/達到/);
  assert.match(explain('sahm_rule',series([.3,.5],'百分點'),365,now).meaning,/非官方/);
});
test('return-index definitions disclose dividends and distinct index coverage',()=>{
  for(const key of ['largecap_equal_weight_trend','nasdaq100_equal_weight_trend','semiconductor_trend'])assert.match(guides[key].definition,/總報酬/);
  assert.match(guides.largecap_equal_weight_trend.definition,/不是 S&P 500/);
});
