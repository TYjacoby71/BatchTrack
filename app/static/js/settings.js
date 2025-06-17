// Settings functionality moved to Alpine.js in the template
// This file is no longer needed

// Bulk save all containers
    async function saveAllContainers() {
        const containers = [];
        const containerRows = document.querySelectorAll('#containerTableBody tr');

        containerRows.forEach(row => {
            const id = row.querySelector('input[name$="[id]"]')?.value;
            const name = row.querySelector('input[name$="[name]"]')?.value;
            const storageAmount = row.querySelector('input[name$="[storage_amount]"]')?.value;
            const storageUnit = row.querySelector('select[name$="[storage_unit]"]')?.value;
            const costPerUnit = row.querySelector('input[name$="[cost_per_unit]"]')?.value;

            if (id && name) {
                containers.push({
                    id: parseInt(id),
                    name: name.trim(),
                    storage_amount: parseFloat(storageAmount) || 0,
                    storage_unit: storageUnit,
                    cost_per_unit: parseFloat(costPerUnit) || 0
                });
            }
        });

        if (containers.length === 0) {
            alert('No containers to update');
            return;
        }

        try {
            const response = await fetch('/settings/bulk-update-containers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name=csrf-token]').getAttribute('content')
                },
                body: JSON.stringify({ containers: containers })
            });

            const result = await response.json();

            if (response.ok) {
                alert(`Successfully updated ${result.updated_count} containers`);
                location.reload(); // Refresh to show updated data
            } else {
                throw new Error(result.error || 'Update failed');
            }
        } catch (error) {
            console.error('Container save error:', error);
            alert('Failed to update containers: ' + error.message);
        }
    }

    window.saveAllSettings = saveAllSettings;
    window.saveAllContainers = saveAllContainers;
});