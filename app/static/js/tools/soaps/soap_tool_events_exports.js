(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { round, toNumber, clamp } = SoapTool.helpers;
  const { formatWeight, formatPercent, toGrams } = SoapTool.units;
  const state = SoapTool.state;

  async function getCalcForExport(){
    const calc = state.lastCalc || await SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: true });
    if (!calc) {
      if (SoapTool.ui?.showSoapAlert) {
        SoapTool.ui.showSoapAlert('warning', 'Run a calculation before exporting or printing.', { dismissible: true, timeoutMs: 6000 });
      }
      return null;
    }
    return calc;
  }

  function collectFragranceExportRows(totalOils){
    const rows = [];
    document.querySelectorAll('#fragranceRows .fragrance-row').forEach(row => {
      const name = row.querySelector('.fragrance-typeahead')?.value?.trim();
      const gramsInput = row.querySelector('.fragrance-grams')?.value;
      const pctInput = row.querySelector('.fragrance-percent')?.value;
      let grams = toGrams(gramsInput);
      let pct = clamp(toNumber(pctInput), 0);
      if (grams <= 0 && pct > 0 && totalOils > 0) {
        grams = totalOils * (pct / 100);
      }
      if (grams <= 0 && pct <= 0 && !name) return;
      if (!pct && grams > 0 && totalOils > 0) {
        pct = (grams / totalOils) * 100;
      }
      rows.push({
        name: name || 'Fragrance/Essential Oils',
        grams,
        pct,
      });
    });
    return rows;
  }

  function collectAdditiveExportRows(additives){
    const rows = [];
    if (!additives) return rows;
    const lactateName = document.getElementById('additiveLactateName')?.value?.trim() || 'Sodium Lactate';
    const sugarName = document.getElementById('additiveSugarName')?.value?.trim() || 'Sugar';
    const saltName = document.getElementById('additiveSaltName')?.value?.trim() || 'Salt';
    const citricName = document.getElementById('additiveCitricName')?.value?.trim() || 'Citric Acid';
    if (additives.lactateG > 0) {
      rows.push({ name: lactateName, grams: additives.lactateG, pct: additives.lactatePct });
    }
    if (additives.sugarG > 0) {
      rows.push({ name: sugarName, grams: additives.sugarG, pct: additives.sugarPct });
    }
    if (additives.saltG > 0) {
      rows.push({ name: saltName, grams: additives.saltG, pct: additives.saltPct });
    }
    if (additives.citricG > 0) {
      rows.push({ name: citricName, grams: additives.citricG, pct: additives.citricPct });
    }
    return rows;
  }

  function buildAssumptionNotes(calc){
    const notes = [];
    const extraLye = toNumber(calc.additives?.citricLyeG);
    const citricG = toNumber(calc.additives?.citricG);
    const lyeType = String(calc.lyeType || 'NaOH').toUpperCase();
    if (extraLye > 0 && citricG > 0) {
      if (lyeType === 'KOH') {
        notes.push('Citric-acid lye adjustment used 0.71 x citric acid because KOH was selected.');
      } else {
        notes.push('Citric-acid lye adjustment used 0.624 x citric acid because NaOH was selected.');
      }
      notes.push(`${formatWeight(extraLye)} lye added extra to accommodate the extra citrus.`);
    }
    if (calc.usedSapFallback) {
      notes.push('Average SAP fallback was used for oils missing SAP values.');
    }
    if (String(calc.lyeSelected || '').toUpperCase() === 'KOH90') {
      notes.push('KOH90 selection assumes 90% lye purity.');
    }
    const oils = Array.isArray(calc.oils) ? calc.oils : [];
    const hasDecimalSap = oils.some(oil => {
      const sap = toNumber(oil?.sapKoh);
      return sap > 0 && sap <= 1;
    });
    if (hasDecimalSap) {
      notes.push('SAP values at or below 1.0 were treated as decimal SAP and converted to mg KOH/g.');
    }
    return notes;
  }

  function buildFormulaCsv(calc){
    if (Array.isArray(calc?.export?.csv_rows) && calc.export.csv_rows.length) {
      return calc.export.csv_rows;
    }
    const totalOils = calc.totalOils || 0;
    const rows = [['section', 'name', 'quantity', 'unit', 'percent']];
    rows.push(['Summary', 'Lye Type', calc.lyeType || '', '', '']);
    rows.push(['Summary', 'Superfat', round(calc.superfat || 0, 2), '%', '']);
    rows.push(['Summary', 'Lye Purity', round(calc.purity || 0, 1), '%', '']);
    rows.push(['Summary', 'Water Method', calc.waterMethod || '', '', '']);
    rows.push(['Summary', 'Water %', round(calc.waterPct || 0, 1), '%', '']);
    rows.push(['Summary', 'Lye Concentration', round(calc.lyeConcentration || 0, 1), '%', '']);
    rows.push(['Summary', 'Water Ratio', round(calc.waterRatio || 0, 2), '', '']);
    rows.push(['Summary', 'Total Oils', round(totalOils, 2), 'gram', '']);
    rows.push(['Summary', 'Batch Yield', round(calc.batchYield || 0, 2), 'gram', '']);

    (calc.oils || []).forEach(oil => {
      const pct = totalOils > 0 ? round((oil.grams / totalOils) * 100, 2) : '';
      rows.push(['Oils', oil.name || 'Oil', round(oil.grams || 0, 2), 'gram', pct]);
    });
    const extraLye = toNumber(calc.additives?.citricLyeG);
    const hasBaseLye = calc.lyeAdjustedBase !== null && calc.lyeAdjustedBase !== undefined && calc.lyeAdjustedBase !== '';
    const totalLye = hasBaseLye
      ? (toNumber(calc.lyeAdjustedBase) + extraLye)
      : toNumber(calc.lyeAdjusted);
    if (totalLye > 0) {
      let lyeLabel = calc.lyeType === 'KOH' ? 'Potassium Hydroxide (KOH)' : 'Sodium Hydroxide (NaOH)';
      if (extraLye > 0) {
        lyeLabel += '*';
      }
      rows.push(['Lye', lyeLabel, round(totalLye, 2), 'gram', '']);
    }
    if (calc.water > 0) {
      rows.push(['Water', 'Distilled Water', round(calc.water, 2), 'gram', '']);
    }
    const fragrances = collectFragranceExportRows(totalOils);
    fragrances.forEach(row => {
      rows.push(['Fragrance', row.name, round(row.grams || 0, 2), 'gram', round(row.pct || 0, 2)]);
    });
    const additiveRows = collectAdditiveExportRows(calc.additives);
    additiveRows.forEach(row => {
      rows.push(['Additives', row.name, round(row.grams || 0, 2), 'gram', round(row.pct || 0, 2)]);
    });
    buildAssumptionNotes(calc).forEach(note => {
      rows.push(['Notes', `* ${note}`, '', '', '']);
    });
    return rows;
  }

  function csvEscape(value){
    if (value === null || value === undefined) return '';
    const str = String(value);
    if (/[",\n]/.test(str)) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  }

  function buildCsvString(rows){
    return rows.map(row => row.map(csvEscape).join(',')).join('\n');
  }

  function triggerCsvDownload(csvText, filename){
    const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function buildPrintSheet(calc){
    if (typeof calc?.export?.sheet_html === 'string' && calc.export.sheet_html.trim()) {
      return calc.export.sheet_html;
    }
    const totalOils = calc.totalOils || 0;
    const oils = (calc.oils || []).map(oil => ({
      name: oil.name || 'Oil',
      grams: oil.grams || 0,
      pct: totalOils > 0 ? (oil.grams / totalOils) * 100 : 0,
    }));
    const fragrances = collectFragranceExportRows(totalOils);
    const additives = collectAdditiveExportRows(calc.additives);
    const now = new Date().toLocaleString();
    const oilRows = oils.length
      ? oils.map(oil => `
          <tr>
            <td>${oil.name}</td>
            <td class="text-end">${formatWeight(oil.grams)}</td>
            <td class="text-end">${formatPercent(oil.pct)}</td>
          </tr>`).join('')
      : '<tr><td colspan="3" class="text-muted">No oils added.</td></tr>';
    const fragranceRows = fragrances.length
      ? fragrances.map(item => `
          <tr>
            <td>${item.name}</td>
            <td class="text-end">${formatWeight(item.grams)}</td>
            <td class="text-end">${formatPercent(item.pct)}</td>
          </tr>`).join('')
      : '<tr><td colspan="3" class="text-muted">No fragrances added.</td></tr>';
    const additiveRows = additives.length
      ? additives.map(item => `
          <tr>
            <td>${item.name}</td>
            <td class="text-end">${formatWeight(item.grams)}</td>
            <td class="text-end">${formatPercent(item.pct)}</td>
          </tr>`).join('')
      : '<tr><td colspan="3" class="text-muted">No additives added.</td></tr>';
    const extraLye = toNumber(calc.additives?.citricLyeG);
    const hasBaseLye = calc.lyeAdjustedBase !== null && calc.lyeAdjustedBase !== undefined && calc.lyeAdjustedBase !== '';
    const totalLye = hasBaseLye
      ? (toNumber(calc.lyeAdjustedBase) + extraLye)
      : toNumber(calc.lyeAdjusted);
    const lyeLabel = `${calc.lyeType === 'KOH' ? 'Potassium Hydroxide (KOH)' : 'Sodium Hydroxide (NaOH)'}${extraLye > 0 ? '*' : ''}`;
    const lyeWeightLabel = `${formatWeight(totalLye)}${extraLye > 0 ? '*' : ''}`;
    const assumptionNotes = buildAssumptionNotes(calc);
    const assumptionsHtml = assumptionNotes.map(note => `<div class="footnote">* ${note}</div>`).join('');
    const assumptionsBlockHtml = assumptionNotes.length
      ? `<div class="footnotes"><h2 class="footnotes-heading">Assumptions</h2>${assumptionsHtml}</div>`
      : '';

    return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Soap Formula Sheet</title>
    <style>
      body { font-family: Arial, sans-serif; color: #111; margin: 24px; }
      h1 { font-size: 20px; margin-bottom: 4px; }
      h2 { font-size: 16px; margin-top: 20px; }
      .meta { font-size: 12px; color: #555; margin-bottom: 12px; }
      table { width: 100%; border-collapse: collapse; margin-top: 8px; }
      th, td { border: 1px solid #ddd; padding: 6px 8px; font-size: 12px; }
      th { background: #f3f4f6; text-align: left; }
      .text-end { text-align: right; }
      .summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 16px; font-size: 12px; }
      .summary-item { display: flex; justify-content: space-between; border-bottom: 1px solid #eee; padding: 4px 0; }
      .text-muted { color: #666; }
      .footnotes { margin-top: 10px; }
      .footnotes-heading { font-size: 14px; margin: 12px 0 4px; }
      .footnote { font-size: 11px; color: #555; margin-top: 6px; }
    </style>
  </head>
  <body>
    <h1>Soap Formula Sheet</h1>
    <div class="meta">Generated ${now}</div>
    <div class="summary-grid">
      <div class="summary-item"><span>Lye type</span><span>${calc.lyeType || '--'}</span></div>
      <div class="summary-item"><span>Superfat</span><span>${formatPercent(calc.superfat || 0)}</span></div>
      <div class="summary-item"><span>Lye purity</span><span>${formatPercent(calc.purity || 0)}</span></div>
      <div class="summary-item"><span>Total oils</span><span>${formatWeight(totalOils)}</span></div>
      <div class="summary-item"><span>Water</span><span>${formatWeight(calc.water || 0)}</span></div>
      <div class="summary-item"><span>Batch yield</span><span>${formatWeight(calc.batchYield || 0)}</span></div>
      <div class="summary-item"><span>Water method</span><span>${calc.waterMethod || '--'}</span></div>
      <div class="summary-item"><span>Lye concentration</span><span>${formatPercent(calc.lyeConcentration || 0)}</span></div>
    </div>

    <h2>Oils</h2>
    <table>
      <thead>
        <tr><th>Oil</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr>
      </thead>
      <tbody>${oilRows}</tbody>
    </table>

    <h2>Lye & Water</h2>
    <table>
      <thead>
        <tr><th>Item</th><th class="text-end">Weight</th></tr>
      </thead>
      <tbody>
        <tr><td>${lyeLabel}</td><td class="text-end">${lyeWeightLabel}</td></tr>
        <tr><td>Distilled Water</td><td class="text-end">${formatWeight(calc.water || 0)}</td></tr>
      </tbody>
    </table>

    <h2>Fragrance & Essential Oils</h2>
    <table>
      <thead>
        <tr><th>Fragrance</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr>
      </thead>
      <tbody>${fragranceRows}</tbody>
    </table>

    <h2>Additives</h2>
    <table>
      <thead>
        <tr><th>Additive</th><th class="text-end">Weight</th><th class="text-end">Percent</th></tr>
      </thead>
      <tbody>${additiveRows}</tbody>
    </table>
    ${assumptionsBlockHtml}
  </body>
</html>`;
  }

  function bind(){
    const saveSoapToolBtn = document.getElementById('saveSoapTool');
    if (saveSoapToolBtn) {
      saveSoapToolBtn.addEventListener('click', async function(){
        try {
          const calc = state.lastCalc || await SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: true });
          if (!calc) return;
          const payload = SoapTool.runner.buildSoapRecipePayload(calc);
          state.lastRecipePayload = payload;
          try {
            const storage = SoapTool.helpers.getStorage();
            if (storage) {
              storage.setItem('soap_recipe_payload', JSON.stringify(payload));
            }
          } catch (_) {}
          window.SOAP_RECIPE_DTO = payload;
          SoapTool.ui.showSoapAlert('info', 'Recipe payload is ready. Push is stubbed for now; no data has been sent.', { dismissible: true, timeoutMs: 7000 });
        } catch(_) {
          SoapTool.ui.showSoapAlert('danger', 'Unable to prepare the recipe payload. Please try again.', { dismissible: true, persist: true });
        }
      });
    }

    const exportSoapCsvBtn = document.getElementById('exportSoapCsv');
    if (exportSoapCsvBtn) {
      exportSoapCsvBtn.addEventListener('click', async function(){
        const calc = await getCalcForExport();
        if (!calc) return;
        const rows = buildFormulaCsv(calc);
        const csvText = (typeof calc?.export?.csv_text === 'string' && calc.export.csv_text)
          ? calc.export.csv_text
          : buildCsvString(rows);
        triggerCsvDownload(csvText, 'soap_formula.csv');
      });
    }

    const printSoapSheetBtn = document.getElementById('printSoapSheet');
    if (printSoapSheetBtn) {
      printSoapSheetBtn.addEventListener('click', async function(){
        const calc = await getCalcForExport();
        if (!calc) return;
        const html = buildPrintSheet(calc);
        const win = window.open('', '_blank', 'width=960,height=720');
        if (!win) {
          if (SoapTool.ui?.showSoapAlert) {
            SoapTool.ui.showSoapAlert('warning', 'Pop-up blocked. Allow pop-ups to print the sheet.', { dismissible: true, timeoutMs: 6000 });
          }
          return;
        }
        win.document.open();
        win.document.write(html);
        win.document.close();
        win.focus();
        win.onload = () => {
          win.print();
        };
      });
    }
  }

  SoapTool.eventsExports = {
    bind,
  };
})(window);
