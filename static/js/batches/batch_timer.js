
// Batch timer functionality 
function addTimerRow() {
  const timerList = document.getElementById('timer-list');
  const timerCount = timerList.children.length;
  
  const timerRow = document.createElement('div');
  timerRow.className = 'timer-row d-flex gap-2 mb-2';
  timerRow.innerHTML = `
    <input type="text" name="timers[${timerCount}][name]" class="form-control" placeholder="Timer Name">
    <input type="number" name="timers[${timerCount}][duration_seconds]" class="form-control" placeholder="Duration (seconds)">
    <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.remove()">✕</button>
  `;
  
  timerList.appendChild(timerRow);
}
