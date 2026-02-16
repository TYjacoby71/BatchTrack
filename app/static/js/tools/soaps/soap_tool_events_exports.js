(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};
  const { toNumber } = SoapTool.helpers;
  const state = SoapTool.state;

  function hasExportPayload(calc){
    return (
      calc
      && typeof calc === 'object'
      && calc.export
      && typeof calc.export.csv_text === 'string'
      && calc.export.csv_text.trim()
      && typeof calc.export.sheet_html === 'string'
      && calc.export.sheet_html.trim()
    );
  }

  function isCalcStale(calc){
    const calcTotalOils = toNumber(calc?.totalOils);
    const currentTotalOils = SoapTool.oils?.getTotalOilsGrams ? SoapTool.oils.getTotalOilsGrams() : 0;
    if (calcTotalOils <= 0 || currentTotalOils <= 0) {
      return false;
    }
    return Math.abs(calcTotalOils - currentTotalOils) > 0.01;
  }

  async function getCalcForExport(){
    let calc = state.lastCalc;
    if (!calc || isCalcStale(calc) || !hasExportPayload(calc)) {
      calc = await SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: true });
    }
    if (!calc) {
      if (SoapTool.ui?.showSoapAlert) {
        SoapTool.ui.showSoapAlert('warning', 'Run a calculation before exporting or printing.', { dismissible: true, timeoutMs: 6000 });
      }
      return null;
    }
    if (!hasExportPayload(calc)) {
      if (SoapTool.ui?.showSoapAlert) {
        SoapTool.ui.showSoapAlert('danger', 'Export payload is missing. Please run the calculation again.', { dismissible: true, timeoutMs: 6000 });
      }
      return null;
    }
    return calc;
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

  function openPrintWindow(html){
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
    win.onload = () => win.print();
  }

  function bindSavePayloadButton(){
    const saveSoapToolBtn = document.getElementById('saveSoapTool');
    if (!saveSoapToolBtn) return;
    saveSoapToolBtn.addEventListener('click', async function(){
      try {
        const calc = state.lastCalc || await SoapTool.runner.calculateAll({ consumeQuota: false, showAlerts: true });
        if (!calc) return;
        const payload = await SoapTool.runner.buildSoapRecipePayload(calc);
        if (!payload) {
          SoapTool.ui.showSoapAlert('danger', 'Unable to prepare the recipe payload. Please try again.', { dismissible: true, persist: true });
          return;
        }
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

  function bindCsvButton(){
    const exportSoapCsvBtn = document.getElementById('exportSoapCsv');
    if (!exportSoapCsvBtn) return;
    exportSoapCsvBtn.addEventListener('click', async function(){
      const calc = await getCalcForExport();
      if (!calc) return;
      triggerCsvDownload(calc.export.csv_text, 'soap_formula.csv');
    });
  }

  function bindPrintButton(){
    const printSoapSheetBtn = document.getElementById('printSoapSheet');
    if (!printSoapSheetBtn) return;
    printSoapSheetBtn.addEventListener('click', async function(){
      const calc = await getCalcForExport();
      if (!calc) return;
      openPrintWindow(calc.export.sheet_html);
    });
  }

  function bind(){
    bindSavePayloadButton();
    bindCsvButton();
    bindPrintButton();
  }

  SoapTool.eventsExports = {
    bind,
  };
})(window);
