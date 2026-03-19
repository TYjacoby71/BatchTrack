
// Unit conversion functionality
async function requestDensityDecision(fromUnit, toUnit) {
  const message =
    `You're converting ${fromUnit} to ${toUnit}, which requires a density.\n` +
    `This ingredient does not have one defined.\n\n` +
    `Use default water density (1.0 g/mL) for this conversion?`;

  if (typeof window.showConfirmDialog === 'function') {
    return window.showConfirmDialog({
      title: 'Density required',
      message,
      confirmText: 'Use water density',
      cancelText: 'Cancel',
      confirmVariant: 'primary',
    });
  }

  if (typeof window.showAlert === 'function') {
    window.showAlert('warning', 'Density decision dialog is unavailable.');
  }
  return false;
}

function showConversionMessage(type, message) {
  if (typeof window.showAlert === 'function') {
    window.showAlert(type, message);
  } else {
    console.log(`[${type}] ${message}`);
  }
}

async function convertUnits() {
  const amount = document.getElementById('amount').value;
  const fromUnit = document.getElementById('fromUnit').value;
  const toUnit = document.getElementById('toUnit').value;
  const ingredientId = document.getElementById('ingredientId').value;
  const resultDiv = document.getElementById('converterResult');

  try {
    const response = await fetch(`/convert/convert/${amount}/${fromUnit}/${toUnit}?ingredient_id=${ingredientId}`);
    const data = await response.json();

    if (data.error && data.error.includes('without density')) {
      const useDefault = await requestDensityDecision(fromUnit, toUnit);
      if (useDefault) {
        const fallbackResponse = await fetch(`/convert/convert/${amount}/${fromUnit}/${toUnit}?ingredient_id=${ingredientId}&density=1.0`);
        const result = await fallbackResponse.json();
        displayResult(resultDiv, `${amount} ${fromUnit} = ${result.result} ${result.unit}`);
        return;
      }
      resultDiv.innerHTML = '<p class="text-danger">Conversion canceled.</p>';
      return;
    }

    displayResult(resultDiv, `${amount} ${fromUnit} = ${data.result} ${data.unit}`);
  } catch (err) {
    resultDiv.innerHTML = `<p class="text-danger">Error: ${err.message}</p>`;
    showConversionMessage('danger', `Conversion failed: ${err.message}`);
  }
}

function displayResult(element, text) {
  element.innerHTML = `
    <p>${text}</p>
    <button class="btn btn-sm btn-secondary" onclick="copyToClipboard('${text}')">Copy</button>
  `;
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    if (typeof window.showToast === 'function') {
      window.showToast('Copied to clipboard.', { type: 'success', title: 'Copied' });
      return;
    }
    showConversionMessage('success', 'Copied to clipboard.');
  }).catch(err => {
    console.error('Failed to copy:', err);
  });
}
