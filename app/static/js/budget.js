document.addEventListener('DOMContentLoaded', function() {
    var groups = document.querySelectorAll('.budget-group');
    groups.forEach(function(group) {
        var total = parseInt(group.dataset.total) || 100;
        var sliders = group.querySelectorAll('.budget-slider');
        var inputs = group.querySelectorAll('.budget-input');
        var remaining = group.querySelector('.remaining-points');

        function updateRemaining() {
            var sum = 0;
            inputs.forEach(function(inp) {
                sum += parseInt(inp.value) || 0;
            });
            var left = total - sum;
            remaining.textContent = left;
            remaining.parentElement.className = left === 0 ? 'alert alert-success' :
                left < 0 ? 'alert alert-danger' : 'alert alert-info';
        }

        sliders.forEach(function(slider, i) {
            slider.addEventListener('input', function() {
                inputs[i].value = this.value;
                updateRemaining();
            });
        });

        inputs.forEach(function(input, i) {
            input.addEventListener('input', function() {
                sliders[i].value = this.value;
                updateRemaining();
            });
        });

        updateRemaining();
    });
});
