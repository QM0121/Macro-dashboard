/* Plain-language, deterministic readings of the displayed observations.
 * Educational context is separate from observed changes; no return forecasts.
 */
(function (root) {
  'use strict';
  const DAY = 86400000;
  const SOURCES = {
    volatility: ['Cboe：VIX 說明', 'https://www.cboe.com/tradable_products/vix/faqs'],
    conditions: ['Chicago Fed：NFCI 定義', 'https://www.chicagofed.org/research/data/nfci/about'],
    inflation: ['Fed：PCE 與通膨目標', 'https://www.federalreserve.gov/faqs/economy_14400.htm'],
    cpi: ['BLS：CPI 問與答', 'https://www.bls.gov/cpi/questions-and-answers.htm'],
    ppi: ['BLS：PPI 問與答', 'https://www.bls.gov/ppi/faqs/questions-and-answers.htm'],
    consumption: ['BEA：消費資料定義', 'https://www.bea.gov/news/pio-release-additional-information'],
    labor: ['BLS：就業資料說明', 'https://www.bls.gov/news.release/empsit.faq.htm'],
    rrp: ['New York Fed：逆回購說明', 'https://www.newyorkfed.org/markets/rrp_faq']
  };
  const guides = {};
  function add(keys, definition, watch, caution, source) {
    keys.forEach(key => { guides[key] = {definition, watch, caution, source}; });
  }
  add(['rate'], '銀行間無擔保隔夜資金的有效成交利率，反映短端資金成本。',
    '看利率變動是否伴隨通膨降溫或就業轉弱，兩種背景的投資意義不同。',
    '這是有效利率，不是政策目標區間；日常小幅波動不等於正式升降息。');
  add(['yield_curve'], '美國十年期公債殖利率減兩年期殖利率；負值稱為倒掛。',
    '看曲線的方向與變化原因，再搭配就業和信用利差。',
    '轉正可能來自長端上升或短端下降，單靠這條利差無法辨識原因，也不能判定景氣已復甦。');
  add(['fed_assets'], '聯準會資產負債表的總資產規模，這裡以兆美元顯示。',
    '觀察數週至數月的增減，搭配資產組成、準備金及金融條件。',
    '資產增加不必然等於啟動 QE，也不保證資金會流入股票。');
  add(['fed_assets_month_change'], '最新一期 Fed 總資產減四週前總資產，正值是增加，負值是縮減。',
    '看近四週增減是否持續；相鄰資料的四週區間會重疊。',
    '這不是曆月變動；不要將每週顯示的四週變動直接加總。');
  add(['reserves'], '存款機構在聯準會持有的準備金餘額，並非股市可動用資金的總額。',
    '搭配短端利率、Fed 資產及逆回購，觀察銀行體系資金環境。',
    '餘額下降本身不足以判定流動性危機，也不能直接換算成股票漲跌。');
  add(['rrp'], '市場參與者使用聯準會隔夜逆回購工具的規模，反映一種短期現金配置。',
    '搭配銀行準備金與短期利率，了解資金在工具之間的移動。',
    '規模下降不代表同額資金流入股市；它也不是整體市場流動性的完整量度。', SOURCES.rrp);
  add(['nfci'], '綜合貨幣、債券、股票及銀行等市場的每週金融條件指數。',
    '零是歷史平均；負值較寬鬆、正值較緊。方向和水位要分開看。',
    '負值上升仍可能代表環境正在收緊，不能只看到負值就當成利多。', SOURCES.conditions);
  add(['hy_spread'], '美國非投資等級公司債的選擇權調整利差，反映相對公債的風險補償。',
    '看利差是否持續擴大，並與股價及金融條件交叉確認。',
    '利差不是債券殖利率，也不是違約機率；1 個百分點等於 100 個基點。');
  add(['vix'], '由 S&P 500 選擇權價格推算的未來約三十天預期波動率，採年化表示。',
    '看市場預期波動是否升高，以及變化是否持續。',
    'VIX 衡量預期波動，不預測漲跌方向，也不是未來三十天的預期跌幅。', SOURCES.volatility);

  add(['pce', 'core_pce'], 'PCE 年增率是消費物價與一年前相比的變化；核心 PCE 排除食品及能源。',
    '看漲速是否持續放緩，再搭配近期月增與三個月年化率。',
    '年增率下降不等於物價下降。Fed 的長期 2% 目標指整體 PCE 年增率，不能直接套在每個通膨指標。', SOURCES.inflation);
  add(['core_pce_3m'], '將最近三個月核心 PCE 價格變化換算成一年速度，呈現較近期的通膨動能。',
    '與核心 PCE 年增率對照，觀察近期漲速是否偏離較長期趨勢。',
    '年化率是假設近期速度延續的換算，不是未來一年通膨預測。', SOURCES.inflation);
  add(['cpi', 'core_cpi'], 'CPI 衡量都市消費者購買商品與服務的價格變化；核心 CPI 排除食品及能源。',
    '圖中是年增率，應搭配月增率、項目組成及 PCE 一起看。',
    '年增率放慢表示漲速降低，不代表價格回到過去水準；CPI 與 PCE 的範圍及權重不同。', SOURCES.cpi);
  add(['ppi'], 'PPI 衡量國內生產者收到的銷售價格變化；此圖使用最終需求 PPI 年增率。',
    '與 CPI、PCE 及企業財報比較，觀察價格壓力是否擴散。',
    '這不是單純原料成本指數；PPI 上升也不代表會等幅轉嫁給消費者。', SOURCES.ppi);

  add(['nonfarm_payrolls'], '美國非農薪資就業的單月淨變動；正值代表當月工作數增加，單位為千人。',
    '搭配三個月平均、失業率及資料修正，降低單月波動干擾。',
    '新增變少仍可能是淨增加；這不是失業人口數，也不能靠單月數字宣布衰退。', SOURCES.labor);
  add(['unemployment_rate'], '失業者占勞動力的比率；勞動力包含就業者及失業者。',
    '看數月方向，搭配非農、勞動參與情況及 Sahm Rule。',
    '失業率受就業與勞動力變動共同影響，與請領失業金人數不是同一個概念。', SOURCES.labor);
  add(['initial_claims'], '首次申請失業保險給付的人數，是週頻率的勞動市場指標。',
    '以四週平均搭配非農與失業率，辨識上升是否持續。',
    '每週波動可能受假期等因素影響；初領人數不是全部失業人口。');
  add(['sahm_rule'], '失業率三個月平均相對過去十二個月三個月平均低點的差距，單位為百分點。',
    '0.5 個百分點是這項規則的衰退警訊門檻，需配合其他就業資料。',
    '這是依歷史關係建立的警訊，不是官方衰退認定，也不是股市跌幅預測。');

  add(['retail_sales', 'retail_sales_yoy'], '零售銷售以名目金額衡量零售及餐飲銷售；月增率與年增率的比較基期不同。',
    '搭配通膨與實質消費，分辨銷售金額變化和實際需求變化。',
    '名目銷售增加可能包含價格上升；零售也不涵蓋全部消費服務。', SOURCES.consumption);
  add(['real_pce', 'real_pce_yoy'], '實質個人消費支出排除物價變化，涵蓋商品與服務的消費。',
    '搭配就業及零售銷售，觀察需求是持續變化，還是單月波動。',
    '月增率表示較前月、年增率表示較一年前；單月改善不代表趨勢已確立。', SOURCES.consumption);

  const stocks = {
    sp500_trend: 'S&P 500 大型美股價格指數，常作為廣泛市場的參考。',
    nasdaq100_trend: 'Nasdaq-100 價格指數，追蹤 Nasdaq 上市的大型非金融公司，並非純科技指數。',
    nasdaq_composite_trend: 'Nasdaq Composite 綜合價格指數，觀察 Nasdaq 上市股票的整體表現。',
    largecap_equal_weight_trend: 'Nasdaq US 500 Large Cap 等權重總報酬指數，包含股息再投資效果；不是 S&P 500 等權重指數。',
    nasdaq100_equal_weight_trend: 'Nasdaq-100 等權重總報酬指數，減少大型成分股權重差異，並包含股息再投資效果。',
    nasdaq_tech_trend: 'Nasdaq-100 Technology Sector 指數，觀察 Nasdaq-100 中科技類股的表現。',
    semiconductor_trend: 'PHLX 半導體總報酬指數，包含股息再投資效果，與常見的 SOX 價格指數點位不同。'
  };
  Object.entries(stocks).forEach(([key, definition]) => add([key], definition,
    '比較期間報酬、距高點回撤與 200 日均線，再對照其他市場分項。',
    '均線是落後指標；不同指數的基期及是否含股息不同，不宜直接比較點位高低。'));

  const parse = stamp => Date.parse(`${stamp}T00:00:00Z`);
  const number = value => new Intl.NumberFormat('zh-TW', {maximumFractionDigits:2}).format(value);
  function explain(key, series, days = 365, now = Date.now()) {
    const guide = guides[key];
    const anchor = parse(series?.as_of);
    const points = (series?.points || []).filter(p => Number.isFinite(p.value) && Number.isFinite(parse(p.date)) && parse(p.date) >= anchor - days * DAY).sort((a,b) => parse(a.date)-parse(b.date));
    if (!guide || points.length < 2) return {observation:'有效觀察值不足，暫不解讀走勢。', meaning:'待資料補齊後，再比較水位與變化。', guide};
    const first = points[0], last = points.at(-1), difference = last.value - first.value;
    const direction = Math.abs(difference) < .00005 ? 0 : Math.sign(difference);
    const relative = key.endsWith('_trend') || ['fed_assets', 'reserves', 'rrp'].includes(key);
    const rate = ['%', '百分點'].includes(series.unit);
    const change = relative ? (first.value > 0 ? difference / first.value * 100 : null) : difference;
    const unit = relative ? '%' : rate ? '個百分點' : series.unit === '指數' ? '點' : series.unit;
    const span = (parse(last.date) - parse(first.date)) / DAY;
    const period = span < days * .65 ? '可用期間' : days === 365 ? '圖示一年' : days === 180 ? '圖示半年' : '圖示三個月';
    let observation = change === null ? `${period}起點為零，無法計算百分比變化。`
      : direction === 0 ? `${period}首末值相同；期間內仍可能有波動。`
      : `${period}${direction > 0 ? '上升' : '下降'} ${number(Math.abs(change))} ${unit}（比較首末值）。`;
    if (change !== null && direction !== 0 && Math.abs(change) < .005) observation = `${period}首末值變化不足 0.01 ${unit}。`;
    if (key === 'nonfarm_payrolls') observation = `單月新增工作由圖示起點的 ${number(first.value)} 千人，變為 ${number(last.value)} 千人。`;
    let meaning = guide.watch;
    if (key.endsWith('_trend')) {
      meaning = Number.isFinite(last.ma200) ? `最新值${last.value >= last.ma200 ? '不低於' : '低於'} 200 日均線；這是趨勢參考，仍需比較其他市場分項。` : '均線資料不足，先比較期間表現，再與其他市場分項交叉確認。';
    } else if (key === 'vix') {
      meaning = `預期震盪${direction > 0 ? '較起點提高' : direction < 0 ? '較起點降低' : '首末相近'}，可用來評估持倉波動風險；它不預測漲跌方向。`;
    } else if (key === 'hy_spread') {
      meaning = direction > 0 ? '信用風險補償較起點擴大，企業融資環境可能轉緊；再與股價及金融條件確認。' : direction < 0 ? '信用風險補償較起點收斂，可觀察債市壓力是否持續減輕；仍需搭配股價。' : '信用風險補償首末相近，仍需觀察期間波動與其他金融條件。';
    } else if (key === 'nfci') {
      meaning = `最新值${last.value < 0 ? '低於零，金融條件較歷史平均寬鬆' : last.value > 0 ? '高於零，金融條件較歷史平均緊' : '位於歷史平均附近'}${direction > 0 ? '，但較起點趨緊' : direction < 0 ? '，並較起點寬鬆' : ''}。`;
    } else if (key === 'yield_curve') {
      meaning = last.value < 0 ? '最新曲線仍倒掛；應搭配就業與信用資料，不能由此推定衰退時間。' : '最新長端利率不低於短端；單靠轉正，無法判斷景氣是否已復甦。';
    } else if (key === 'sahm_rule') {
      meaning = last.value >= .5 ? '最新值達到此規則的 0.5 百分點警訊門檻；仍非官方衰退認定。' : '最新值未達此規則的 0.5 百分點門檻；不代表所有景氣風險已解除。';
    } else if (['pce','core_pce','cpi','core_cpi','ppi','core_pce_3m'].includes(key)) {
      meaning = last.value > 0 ? (key === 'ppi' ? '生產者售價仍高於一年前；需觀察是否傳導至消費物價與企業利潤。' : direction > 0 ? '物價漲速較起點加快，可能增加利率維持偏高的壓力；仍需搭配就業背景。' : direction < 0 ? '物價漲速較起點放緩，可觀察通膨壓力是否持續減輕；不代表物價下降。' : '物價仍在上漲，首末漲速相近；需再看近期動能是否改變。') : last.value < 0 ? '最新價格變化率為負，表示本指標對應期間的價格低於比較基期。' : '最新價格變化率接近零，仍需搭配其他期間與物價指標。';
    } else if (key === 'nonfarm_payrolls') {
      meaning = last.value > 0 ? '最新月份仍淨新增工作；新增變少與工作總數減少，是不同的意思。' : last.value < 0 ? '最新月份工作數淨減少；需搭配三個月平均及失業率確認是否持續。' : '最新月份工作數淨變動為零；需觀察後續修正及其他就業資料。';
    } else if (key === 'initial_claims') {
      meaning = `初領申請人數${direction > 0 ? '較起點增加' : direction < 0 ? '較起點減少' : '首末相近'}；看四週平均是否同向，避免只看單週。`;
    } else if (key === 'fed_assets_month_change') {
      meaning = `最新四週資產${last.value > 0 ? '淨增加' : last.value < 0 ? '淨縮減' : '淨變動為零'}；這是滾動四週差額，不是新增的政策宣告。`;
    } else if (key === 'rate') {
      meaning = '利率是企業融資成本與股票估值的背景；需結合通膨及就業，理解變動原因。';
    } else if (key === 'rrp') {
      meaning = '這反映逆回購工具的使用規模；變少並不代表同額資金流入股市。';
    } else if (key === 'fed_assets' || key === 'reserves') {
      meaning = '資金規模變化可作背景參考，需與其他流動性指標一起看，不能直接推算股票報酬。';
    } else if (key.startsWith('real_pce')) {
      meaning = `最新${key.endsWith('_yoy') ? '年' : '月'}增率${last.value > 0 ? '為正，實質消費較比較基期增加' : last.value < 0 ? '為負，實質消費較比較基期減少' : '接近零'}；已排除物價變化。`;
    } else if (key.startsWith('retail_sales')) {
      meaning = `最新名目銷售${last.value > 0 ? '較比較基期增加' : last.value < 0 ? '較比較基期減少' : '接近比較基期'}；仍要分辨價格變化與實際需求。`;
    } else if (key === 'unemployment_rate') {
      meaning = `失業比率${direction > 0 ? '較起點升高' : direction < 0 ? '較起點降低' : '首末相同'}；應與非農及勞動參與情況一起判讀。`;
    }
    const expired = !Number.isFinite(anchor) || now - anchor > ({daily:7,weekly:21,monthly:80}[series.frequency] || 7) * DAY;
    if (series.fetch_status === 'failed' || expired) {
      observation = `來源${series.fetch_status === 'failed' ? '更新失敗' : '資料可能過期'}；${observation}`;
      meaning = '以上只描述現有舊資料，待更新後再評估目前情況。';
    } else if (last.date !== series.as_of) {
      observation = `最新一期換算值缺漏，以下僅比較有效值至 ${last.date}。${observation}`;
    }
    return {observation, meaning, guide};
  }
  const api = {guides, explain};
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.MacroReading = api;
})(typeof window === 'object' ? window : this);
