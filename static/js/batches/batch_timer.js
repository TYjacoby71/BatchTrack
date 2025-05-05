
// Batch timer functionality
function startTimer(timerId, duration) {
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
