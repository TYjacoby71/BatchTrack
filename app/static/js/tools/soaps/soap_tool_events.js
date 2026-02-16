(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};

  function bind(){
    const refs = SoapTool.eventsRows?.bind
      ? SoapTool.eventsRows.bind()
      : { oilRows: null, fragranceRows: null };

    if (SoapTool.eventsForms?.bind) {
      SoapTool.eventsForms.bind(refs);
    }
    if (SoapTool.eventsExports?.bind) {
      SoapTool.eventsExports.bind(refs);
    }
    if (SoapTool.eventsMobile?.bind) {
      SoapTool.eventsMobile.bind(refs);
    }
    if (SoapTool.eventsInit?.bind) {
      SoapTool.eventsInit.bind(refs);
    }
  }

  bind();
})(window);
