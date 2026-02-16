(function(window){
  'use strict';

  const SoapTool = window.SoapTool = window.SoapTool || {};

  function setupMobileDrawer(){
    const drawer = document.getElementById('soapMobileDrawer');
    const drawerContent = document.getElementById('soapMobileDrawerContent');
    const drawerTitle = document.getElementById('soapMobileDrawerTitle');
    const drawerEmpty = document.getElementById('soapDrawerEmpty');
    const closeBtn = document.getElementById('soapDrawerClose');
    const qualityCard = document.getElementById('soapQualityCard');
    const resultsCard = document.getElementById('resultsCard');
    if (!drawer || !drawerContent || !drawerTitle || !qualityCard || !resultsCard) return;

    const qualityHome = qualityCard.parentElement;
    const resultsHome = resultsCard.parentElement;
    const placeholders = new Map();
    let currentTarget = null;

    const isSmallScreen = () => window.matchMedia('(max-width: 767px)').matches;
    const cardForTarget = (target) => (target === 'quality' ? qualityCard : resultsCard);
    const homeForTarget = (target) => (target === 'quality' ? qualityHome : resultsHome);
    const titleForTarget = (target) => (target === 'quality' ? 'Display' : 'Results');

    const ensurePlaceholder = (card) => {
      let placeholder = placeholders.get(card);
      if (!placeholder) {
        placeholder = document.createElement('div');
        placeholder.className = 'soap-card-placeholder';
        placeholders.set(card, placeholder);
      }
      placeholder.style.height = `${card.offsetHeight}px`;
      if (card.parentElement && card.parentElement !== drawerContent && !placeholder.parentElement) {
        card.parentElement.insertBefore(placeholder, card);
      }
    };

    const moveCardToDrawer = (card) => {
      if (!card) return;
      ensurePlaceholder(card);
      drawerContent.appendChild(card);
    };

    const restoreCard = (card, home) => {
      const placeholder = placeholders.get(card);
      if (placeholder && placeholder.parentElement) {
        placeholder.replaceWith(card);
      } else if (home && card.parentElement !== home) {
        home.appendChild(card);
      }
    };

    const updateDrawerEmpty = () => {
      if (!drawerEmpty) return;
      const isResults = currentTarget === 'results';
      const resultsVisible = getComputedStyle(resultsCard).display !== 'none';
      drawerEmpty.classList.toggle('d-none', !isResults || resultsVisible);
    };

    const openDrawer = (target) => {
      if (!isSmallScreen()) return;
      if (currentTarget && currentTarget !== target) {
        restoreCard(cardForTarget(currentTarget), homeForTarget(currentTarget));
      }
      moveCardToDrawer(cardForTarget(target));
      drawerTitle.textContent = titleForTarget(target);
      currentTarget = target;
      drawer.classList.add('is-open');
      updateDrawerEmpty();
    };

    const closeDrawer = () => {
      if (!currentTarget) return;
      restoreCard(cardForTarget(currentTarget), homeForTarget(currentTarget));
      currentTarget = null;
      drawer.classList.remove('is-open');
      updateDrawerEmpty();
    };

    drawer.querySelectorAll('[data-drawer-target]').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.drawerTarget;
        if (!target) return;
        if (drawer.classList.contains('is-open') && currentTarget === target) {
          closeDrawer();
        } else {
          openDrawer(target);
        }
      });
    });

    if (closeBtn) {
      closeBtn.addEventListener('click', closeDrawer);
    }

    window.addEventListener('resize', () => {
      if (!isSmallScreen() && currentTarget) {
        closeDrawer();
      }
    });

    const resultsObserver = new MutationObserver(() => updateDrawerEmpty());
    resultsObserver.observe(resultsCard, { attributes: true, attributeFilter: ['style', 'class'] });
  }

  function bind(){
    setupMobileDrawer();
    window.addEventListener('resize', SoapTool.layout.scheduleStageHeightSync);
    window.addEventListener('load', SoapTool.layout.scheduleStageHeightSync);
  }

  SoapTool.eventsMobile = {
    bind,
  };
})(window);
