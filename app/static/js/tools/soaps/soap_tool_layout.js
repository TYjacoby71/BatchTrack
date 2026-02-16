(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};

  function syncStageHeight(){
    const stagePane = document.getElementById('soapStagePane');
    const qualityCard = document.getElementById('soapQualityCard');
    const stageQualityRow = document.getElementById('soapStageQualityRow');
    const guidanceDock = document.getElementById('soapGuidanceDock');
    if (stageQualityRow && guidanceDock) {
      const rowHeight = stageQualityRow.offsetHeight || 0;
      const overlayHeight = Math.max(280, rowHeight + 96);
      guidanceDock.style.setProperty('--soap-guidance-overlay-height', `${overlayHeight}px`);
    }
    if (!stagePane || !qualityCard) return;
    const shouldSync = window.matchMedia('(min-width: 768px)').matches;
    if (!shouldSync) {
      stagePane.classList.remove('is-height-synced');
      stagePane.style.removeProperty('--soap-stage-height');
      return;
    }
    const qualityHeight = qualityCard.offsetHeight;
    if (!qualityHeight) {
      stagePane.classList.remove('is-height-synced');
      stagePane.style.removeProperty('--soap-stage-height');
      return;
    }
    stagePane.style.setProperty('--soap-stage-height', `${qualityHeight}px`);
    stagePane.classList.add('is-height-synced');
  }

  const scheduleStageHeightSync = () => {
    window.requestAnimationFrame(syncStageHeight);
  };

  SoapTool.layout = {
    syncStageHeight,
    scheduleStageHeightSync,
  };
})(window);
