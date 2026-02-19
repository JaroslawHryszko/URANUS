document.addEventListener('DOMContentLoaded', function() {
    var lists = document.querySelectorAll('.sortable-list');
    lists.forEach(function(list) {
        var param = list.dataset.param;
        Sortable.create(list, {
            animation: 150,
            ghostClass: 'bg-primary-subtle',
            onEnd: function() {
                updateOrder(list, param);
                updateBadges(list);
            }
        });
        // Set initial order
        updateOrder(list, param);
    });

    function updateOrder(list, param) {
        var items = list.querySelectorAll('li[data-id]');
        var ids = Array.from(items).map(function(el) { return el.dataset.id; });
        var input = document.getElementById('order_' + param);
        if (input) input.value = ids.join(',');
    }

    function updateBadges(list) {
        var items = list.querySelectorAll('li[data-id]');
        items.forEach(function(el, idx) {
            var badge = el.querySelector('.rank-badge');
            if (badge) badge.textContent = idx + 1;
        });
    }
});
