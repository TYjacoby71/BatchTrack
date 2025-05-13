
// Timer display functionality
function updateTimerDisplay(timer) {
  if (!timer.start_time || !timer.duration_seconds) return;
  
  const endTime = new Date(timer.start_time).getTime() + (timer.duration_seconds * 1000);
  const now = new Date().getTime();
  const remaining = Math.max(0, endTime - now);
  
  const minutes = Math.floor(remaining / 60000);
  const seconds = Math.floor((remaining % 60000) / 1000);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

document.addEventListener('alpine:init', () => {
  Alpine.data('timerManager', () => ({
    timers: [],
    
    init() {
      // Initialize with any existing timers from the page
      const existingTimers = JSON.parse(document.getElementById('existing-timers')?.dataset?.timers || '[]');
      this.timers = existingTimers.map(timer => ({
        ...timer,
        name: timer.name || '',
        duration_seconds: timer.duration_seconds || null,
        start_time: timer.start_time || null
      }));
    },

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
          timer.status = 'running';
        }
      } catch (error) {
        console.error('Error starting timer:', error);
      }
    }
  }));
});
