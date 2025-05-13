
// Timer management functionality
function addTimerRow() {
  const container = document.getElementById('timer-list');
  const timerCount = container.children.length;
  
  const row = document.createElement('div');
  row.className = 'timer-row d-flex gap-2 mb-2';
  row.innerHTML = `
    <input type="text" name="timer_name" class="form-control" placeholder="Timer Name" required>
    <input type="number" name="duration_minutes" class="form-control" placeholder="Duration (minutes)" required min="1" step="1">
    <button type="button" class="btn btn-primary btn-sm start-timer" onclick="startTimer(this)">▶ Start</button>
    <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.remove()">✕</button>
  `;
  container.appendChild(row);
}

function startTimer(btn) {
  const row = btn.parentElement;
  const nameInput = row.querySelector('input[name="timer_name"]');
  const durationInput = row.querySelector('input[name="duration_minutes"]');
  
  if (!nameInput.value || !durationInput.value) {
    alert('Please fill in both timer name and duration');
    return;
  }

  const timerData = {
    name: nameInput.value,
    duration_seconds: parseInt(durationInput.value) * 60,
    csrf_token: document.querySelector('input[name="csrf_token"]').value
  };

  fetch(`/timers/start/${batchId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': timerData.csrf_token
    },
    body: JSON.stringify(timerData)
  })
  .then(response => response.json())
  .then(data => {
    if (data.status === 'success') {
      const activeTimers = document.getElementById('active-timers');
      const timerElement = document.createElement('div');
      timerElement.className = 'active-timer-row d-flex gap-2 mb-2 align-items-center';
      timerElement.id = `timer-${data.timer_id}`;
      timerElement.innerHTML = `
        <span class="timer-name">${data.name}</span>
        <span class="timer-countdown badge bg-primary"></span>
        <span class="timer-end">Ends: ${new Date(data.end_time).toLocaleTimeString()}</span>
        <button type="button" class="btn btn-outline-danger btn-sm" onclick="cancelTimer(${data.timer_id})">⊗</button>
      `;
      activeTimers.appendChild(timerElement);
      row.remove();
      
      updateTimerCountdown(data.timer_id, new Date(data.end_time));
    }
  })
  .catch(error => {
    console.error('Error starting timer:', error);
    alert('Failed to start timer');
  });
}

function updateTimerCountdown(timerId, endTime) {
  const countdownElement = document.querySelector(`#timer-${timerId} .timer-countdown`);
  
  const interval = setInterval(() => {
    const now = new Date();
    const remaining = endTime - now;
    
    if (remaining <= 0) {
      clearInterval(interval);
      countdownElement.textContent = 'Complete';
      countdownElement.className = 'badge bg-success';
    } else {
      const minutes = Math.floor(remaining / 60000);
      const seconds = Math.floor((remaining % 60000) / 1000);
      countdownElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
  }, 1000);
}

function cancelTimer(timerId) {
  const csrfToken = document.querySelector('input[name="csrf_token"]').value;
  
  fetch(`/timers/cancel/${timerId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.status === 'success') {
      document.querySelector(`#timer-${timerId}`).remove();
    }
  })
  .catch(error => {
    console.error('Error canceling timer:', error);
    alert('Failed to cancel timer');
  });
}

// Initialize any existing timers
document.addEventListener('DOMContentLoaded', () => {
  const activeTimers = document.querySelectorAll('.active-timer-row');
  activeTimers.forEach(timer => {
    const timerId = timer.id.split('-')[1];
    const endTimeElement = timer.querySelector('.timer-end');
    const endTimeStr = endTimeElement.textContent.split(': ')[1];
    const endTime = new Date(endTimeStr);
    
    // Only initialize if timer hasn't ended
    if (endTime > new Date()) {
      updateTimerCountdown(timerId, endTime);
    }
  });
});
