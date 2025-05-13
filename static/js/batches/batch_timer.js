
// Timer display functionality
function startTimerDisplay(timerId, duration) {
  const timerElement = document.getElementById(`timer-${timerId}`);
  if (!timerElement) return;

  const endTime = Date.now() + (duration * 1000);
  
  const timer = setInterval(() => {
    const now = Date.now();
    const remaining = Math.max(0, endTime - now);
    
    if (remaining === 0) {
      clearInterval(timer);
      timerElement.textContent = 'Timer Complete!';
      // Alert or notification logic
    } else {
      const minutes = Math.floor(remaining / 60000);
      const seconds = Math.floor((remaining % 60000) / 1000);
      timerElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
  }, 1000);
}

document.addEventListener('alpine:init', () => {
  Alpine.data('timerManager', () => ({
    timers: Alpine.$data.timers || [],
    
    addTimer() {
      this.timers.push({
        name: '',
        duration_seconds: null,
        start_time: null
      });
    },

    removeTimer(index) {
      this.timers.splice(index, 1);
    },

    async startTimer(timer) {
      if (!timer.duration_seconds) return;
      
      const csrfToken = document.querySelector('input[name="csrf_token"]').value;
      
      try {
        const response = await fetch('/timers/start', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({ 
            timer_id: timer.id,
            duration: timer.duration_seconds
          })
        });
        
        const data = await response.json();
        if (data.success) {
          timer.start_time = new Date().toISOString();
          startTimerDisplay(timer.id, timer.duration_seconds);
        }
      } catch (error) {
        console.error('Error starting timer:', error);
      }
    }
  }));
});
