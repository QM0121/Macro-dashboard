/* Dependency-free SVG charts. The JSON contains observed data, never synthetic points. */
(() => {
  'use strict';
  const GROUPS = [
    ['trend', 'market', ['sp500_trend', 'nasdaq100_trend', 'nasdaq_composite_trend', 'largecap_equal_weight_trend', 'nasdaq100_equal_weight_trend', 'nasdaq_tech_trend', 'semiconductor_trend']],
    ['risk', 'stress', ['vix', 'hy_spread', 'nfci']],
    ['inflation', 'inflation', ['core_pce', 'core_pce_3m', 'pce', 'core_cpi', 'cpi', 'ppi']],
    ['labor', 'labor', ['nonfarm_payrolls', 'unemployment_rate', 'initial_claims', 'sahm_rule']],
    ['liquidity', 'liquidity', ['fed_assets', 'fed_assets_month_change', 'reserves', 'rrp']],
    ['rate', 'rates', ['rate']],
    ['curve', 'curve', ['yield_curve']],
    ['consumption', 'consumption', ['retail_sales', 'retail_sales_yoy', 'real_pce', 'real_pce_yoy']]
  ];
  const escape = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const format = (value, unit) => `${new Intl.NumberFormat('zh-TW', {maximumFractionDigits:unit === '人' || unit === '千人' ? 1 : 3}).format(value)} ${unit}`;
  const dayMs = 86400000;
  const parse = date => Date.parse(`${date}T00:00:00Z`);
  let data, dialog, modalView;

  function init(payload) {
    if (data) return;
    data = payload;
    dialog = document.createElement('dialog');
    dialog.className = 'chart-dialog';
    dialog.innerHTML = '<div class="chart-dialog-head"><h2>歷史走勢</h2><button type="button" class="btn ghost" aria-label="關閉走勢圖">關閉 ×</button></div><div class="chart-dialog-body"></div>';
    document.body.append(dialog);
    dialog.querySelector('button').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', event => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
    dialog.addEventListener('close', () => { modalView?.destroy(); modalView = null; });
    GROUPS.forEach(([card, id, keys]) => {
      const article = document.querySelector(`.detail-${card}`);
      if (!article) return;
      article.id = `history-${id}`;
      const figure = document.createElement('figure');
      figure.className = 'history-chart';
      article.querySelector('.status-line').before(figure);
      createView(figure, keys, keys[0], false);
      const grid = article.querySelector('.inflation-grid, .labor-grid, .liquidity-grid, .risk-grid, .consumption-grid, .trend-grid');
      if (grid) {
        const details = document.createElement('details');
        details.className = 'metric-details';
        details.innerHTML = '<summary>查看最新數值明細</summary>';
        grid.before(details); details.append(grid);
      }
    });
    const fields = {
      'rate-current':'rate','yield-current':'yield_curve','assets-current':'fed_assets','assets-change-current':'fed_assets_month_change',
      'reserves-current':'reserves','rrp-current':'rrp','nfci-current':'nfci','hy-current':'hy_spread','vix-current':'vix','vix-change5':'vix',
      'core-pce-yoy':'core_pce','core-pce-3m':'core_pce','pce-yoy':'pce','core-cpi-yoy':'core_cpi','cpi-yoy':'cpi','ppi-yoy':'ppi',
      'nonfarm-current':'nonfarm_payrolls','nonfarm-avg3m':'nonfarm_payrolls','unemployment-current':'unemployment_rate','unemployment-change3m':'unemployment_rate',
      'claims-current':'initial_claims','claims-avg4w':'initial_claims','sahm-current':'sahm_rule',
      'retail-mom':'retail_sales','retail-yoy':'retail_sales','real-pce-mom':'real_pce','real-pce-yoy':'real_pce',
      'sp-current':'sp500_trend','sp-return5':'sp500_trend','sp-ma20':'sp500_trend','sp-ma50':'sp500_trend','sp-ma200':'sp500_trend','sp-drawdown':'sp500_trend','sp-distance200':'sp500_trend'
    };
    Object.entries(fields).forEach(([id,key]) => {
      const parent = document.getElementById(id)?.closest('.submetric, .metric-main');
      if (!parent) return;
      const stamp = document.createElement('small'); stamp.className = 'observation-date';
      stamp.textContent = `資料：${data[key]?.current_date || '日期不足'}${data.data_health?.snapshot_failures?.includes(key) ? ' · 更新失敗，沿用舊值' : ''}`;
      parent.append(stamp);
    });
    showHealth();
  }

  function showHealth() {
    const node = document.getElementById('data-health');
    if (!node) return;
    const dates = GROUPS[0][2].map(key => data[key]?.current_date).filter(Boolean).sort();
    const failures = new Set([...(data.data_health?.snapshot_failures || []), ...(data.data_health?.history_failures || [])]);
    node.textContent = dates.length ? `市場資料截至 ${dates[0]}${dates.at(-1) !== dates[0] ? `～${dates.at(-1)}（各指數日期不同）` : ''}。` : '市場資料日期不足。';
    if (failures.size) node.textContent += ` ${failures.size} 項資料抓取失敗，圖表已標示並保留可用舊值。`;
    const latest = dates.at(-1);
    if (latest && Date.now() - parse(latest) > 7 * dayMs) node.textContent += ' 市場資料已超過七天，請確認自動更新。';
  }

  function createView(root, keys, initial, expanded, initialDays = 365) {
    let selected = initial, days = initialDays, showMA = true, active = 0;
    root.innerHTML = `<div class="chart-toolbar"><label class="chart-metric-label"><span class="sr-only">選擇指標</span><select aria-label="選擇走勢指標">${keys.map(key => `<option value="${key}">${escape(data.history?.[key]?.label || key)}</option>`).join('')}</select></label><div class="chart-periods" role="group" aria-label="走勢期間">${[[90,'3月'],[180,'6月'],[365,'1年']].map(([value,label]) => `<button type="button" data-days="${value}" aria-pressed="${value === days}">${label}</button>`).join('')}</div>${expanded ? '' : '<button type="button" class="chart-expand" aria-label="放大走勢圖">放大 ↗</button>'}</div><div class="chart-meta"></div><div class="chart-options"></div><output class="chart-readout" aria-live="polite"></output><div class="chart-plot"></div><figcaption class="chart-caption"></figcaption>`;
    const select = root.querySelector('select'); select.value = selected;
    const plot = root.querySelector('.chart-plot');
    const readout = root.querySelector('output');
    select.addEventListener('change', () => { selected = select.value; render(); });
    root.querySelectorAll('[data-days]').forEach(button => button.addEventListener('click', () => {
      days = Number(button.dataset.days);
      root.querySelectorAll('[data-days]').forEach(item => item.setAttribute('aria-pressed', String(Number(item.dataset.days) === days)));
      render();
    }));
    root.querySelector('.chart-expand')?.addEventListener('click', () => {
      dialog.querySelector('h2').textContent = data.history?.[selected]?.label || '歷史走勢';
      modalView?.destroy();
      dialog.showModal();
      modalView = createView(dialog.querySelector('.chart-dialog-body'), keys, selected, true, days);
    });

    function render() {
      const series = data.history?.[selected];
      if (expanded) dialog.querySelector('h2').textContent = series?.label || '歷史走勢';
      const meta = root.querySelector('.chart-meta');
      const options = root.querySelector('.chart-options');
      const caption = root.querySelector('.chart-caption');
      const cutoff = (series?.as_of ? parse(series.as_of) : Date.now()) - days * dayMs;
      const points = (series?.points || []).filter(point => parse(point.date) >= cutoff && Number.isFinite(point.value));
      const frequency = {daily:'日', weekly:'週', monthly:'月'}[series?.frequency] || '';
      const age = series?.as_of ? (Date.now() - parse(series.as_of)) / dayMs : Infinity;
      const overdue = age > ({daily:7, weekly:21, monthly:80}[series?.frequency] || 7);
      const failed = series?.fetch_status === 'failed';
      meta.textContent = `資料截至 ${series?.as_of || '尚無資料'} · ${frequency}資料${failed ? ' · 抓取失敗，沿用舊值' : overdue ? ' · 資料可能過期' : ''}`;
      meta.classList.toggle('is-warning', failed || overdue);
      options.replaceChildren();
      if (selected.endsWith('_trend') && points.length) {
        const label = document.createElement('label');
        label.className = 'ma-toggle';
        const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.checked = showMA;
        checkbox.addEventListener('change', () => { showMA = checkbox.checked; render(); });
        label.append(checkbox, document.createTextNode('200 日均線（虛線）')); options.append(label);
      }
      caption.textContent = points.length ? `${points[0].date} — ${points.at(-1).date} · ${points.length} 筆觀察值 · ${series.unit}${series.frequency === 'monthly' ? ' · 日期為資料所屬月份' : ''}` : '尚無此期間歷史資料；下次資料更新後自動顯示。';
      if (series?.series_id && /^[A-Z0-9]+$/.test(series.series_id)) {
        const link = document.createElement('a'); link.href = `https://fred.stlouisfed.org/series/${series.series_id}`;
        link.textContent = 'FRED 原始資料 ↗'; link.target = '_blank'; link.rel = 'noopener noreferrer'; caption.append(document.createTextNode(' · '), link);
      }
      if (points.length < 2) {
        plot.innerHTML = '<div class="chart-empty">此期間觀察值不足，暫不繪製走勢。</div>';
        readout.textContent = points.length ? `${points[0].date}　${format(points[0].value, series.unit)}` : '等待有效歷史資料'; return;
      }
      const W = Math.max(270, Math.round(plot.clientWidth || 600)), H = expanded ? 380 : 230;
      const margin = {left:57, right:15, top:15, bottom:30};
      const bar = selected === 'nonfarm_payrolls';
      const hasMA = selected.endsWith('_trend') && showMA;
      const values = points.flatMap(point => [point.value, ...(hasMA && Number.isFinite(point.ma200) ? [point.ma200] : [])]);
      const includeZero = bar || selected === 'yield_curve' || ['mom','diff','change4'].includes(series.transform);
      let min = Math.min(...values, ...(includeZero ? [0] : [])), max = Math.max(...values, ...(includeZero ? [0] : []));
      const padding = (max - min || Math.abs(max) * .1 || 1) * .13; min -= padding; max += padding;
      const t0 = parse(points[0].date), t1 = parse(points.at(-1).date);
      const x = point => margin.left + (parse(point.date) - t0) / (t1 - t0) * (W - margin.left - margin.right);
      const y = value => margin.top + (max - value) / (max - min) * (H - margin.top - margin.bottom);
      const short = value => new Intl.NumberFormat('zh-TW', {notation:Math.abs(value) >= 100000 ? 'compact' : 'standard', maximumFractionDigits:Math.abs(max-min)<1 ? 3 : 2}).format(value);
      const limit = {daily:7, weekly:10, monthly:45}[series.frequency] * dayMs;
      function path(field) {
        let result = '', previous = null;
        for (const point of points) {
          if (!Number.isFinite(point[field])) { previous = null; continue; }
          const join = previous && parse(point.date) - parse(previous.date) <= limit;
          result += `${join ? 'L' : 'M'}${x(point).toFixed(2)},${y(point[field]).toFixed(2)} `; previous = point;
        }
        return result;
      }
      let grid = '';
      for (let i = 0; i < 4; i++) {
        const value = min + (max - min) * i / 3, row = y(value);
        grid += `<line class="chart-gridline" x1="${margin.left}" y1="${row}" x2="${W-margin.right}" y2="${row}"/><text x="${margin.left-8}" y="${row+4}" text-anchor="end">${short(value)}</text>`;
      }
      const indices = [0, Math.floor((points.length-1)/2), points.length-1];
      const axis = indices.map((index,i) => `<text x="${x(points[index])}" y="${H-7}" text-anchor="${i === 0 ? 'start' : i === 2 ? 'end' : 'middle'}">${points[index].date.slice(2).replaceAll('-','/')}</text>`).join('');
      const zero = min < 0 && max > 0 ? `<line class="chart-zero" x1="${margin.left}" y1="${y(0)}" x2="${W-margin.right}" y2="${y(0)}"/>` : '';
      const bars = bar ? points.map(point => `<rect class="chart-bar ${point.value < 0 ? 'negative' : ''}" x="${x(point)-Math.min(20,(W-margin.left-margin.right)/points.length*.55)/2}" y="${Math.min(y(0),y(point.value))}" width="${Math.min(20,(W-margin.left-margin.right)/points.length*.55)}" height="${Math.max(1,Math.abs(y(point.value)-y(0)))}"/>`).join('') : `<path class="chart-line" d="${path('value')}"/>`;
      plot.innerHTML = `<svg viewBox="0 0 ${W} ${H}" style="height:${H}px" tabindex="0" role="img" aria-label="${escape(series.label)}近${days}天走勢，${points.length}筆。使用左右方向鍵查看各期數值。">${grid}${zero}${axis}${bars}${hasMA ? `<path class="chart-ma" d="${path('ma200')}"/>` : ''}<line class="chart-cursor" y1="${margin.top}" y2="${H-margin.bottom}"/><circle class="chart-dot" r="4"/><rect class="chart-hit" x="${margin.left}" y="${margin.top}" width="${W-margin.left-margin.right}" height="${H-margin.top-margin.bottom}" fill="transparent"/></svg>`;
      const svg = plot.querySelector('svg');
      active = points.length - 1;
      function inspect(index) {
        active = Math.max(0, Math.min(points.length - 1, index));
        const point = points[active];
        readout.textContent = `${point.date}　${format(point.value, series.unit)}${hasMA && Number.isFinite(point.ma200) ? `　均線 ${format(point.ma200, series.unit)}` : ''}`;
        const cursor = svg.querySelector('.chart-cursor'), dot = svg.querySelector('.chart-dot');
        cursor.setAttribute('x1',x(point));cursor.setAttribute('x2',x(point));dot.setAttribute('cx',x(point));dot.setAttribute('cy',y(point.value));
      }
      svg.addEventListener('pointermove', event => {
        const bounds = svg.getBoundingClientRect();
        const target = (event.clientX - bounds.left) / bounds.width * W;
        let nearest = 0; points.forEach((point,index) => { if (Math.abs(x(point)-target) < Math.abs(x(points[nearest])-target)) nearest = index; }); inspect(nearest);
      });
      svg.addEventListener('keydown', event => {
        if (['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) {
          event.preventDefault();inspect(event.key === 'Home' ? 0 : event.key === 'End' ? points.length-1 : active + (event.key === 'ArrowRight' ? 1 : -1));
        }
      });
      inspect(active);
    }
    let previousWidth = 0;
    const observer = new ResizeObserver(entries => {
      const width = Math.round(entries[0].contentRect.width);
      if (width !== previousWidth) { previousWidth = width; render(); }
    });
    observer.observe(root); render();
    return {destroy: () => observer.disconnect()};
  }
  if (window.dashboardData) init(window.dashboardData);
  else window.addEventListener('dashboard:ready', event => init(event.detail), {once:true});
})();
