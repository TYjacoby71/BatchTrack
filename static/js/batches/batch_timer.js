
// Alpine timer handling
document.addEventListener('alpine:init', () => {
    Alpine.data('timerHandling', () => ({
        async saveTimer() {
            if (!this.newTimerName || !this.newTimerDuration) return;
            
            try {
                const response = await fetch('/timers/start', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                    },
                    body: JSON.stringify({
                        batch_id: document.getElementById('batchForm').dataset.batchId,
                        name: this.newTimerName,
                        duration: this.newTimerDuration
                    })
                });

                if (response.ok) {
                    const timer = await response.json();
                    this.timers.push(timer);
                    this.newTimerName = '';
                    this.newTimerDuration = '';
                    this.addingTimer = false;
                }
            } catch (error) {
                console.error('Error saving timer:', error);
            }
        }
    }));
});
