(function() {
    'use strict';

    var buffer = [];
    var FLUSH_INTERVAL = 5000;
    var HESITATION_THRESHOLD = 10000;
    var lastInteractionTime = performance.now();
    var hesitationTimer = null;
    var pageStartTime = performance.now();

    function getElementInfo(el) {
        if (!el || !el.tagName) return {};
        return {
            element_id: el.id || '',
            element_tag: el.tagName.toLowerCase(),
            element_class: el.className && typeof el.className === 'string' ? el.className.substring(0, 200) : ''
        };
    }

    function pushEvent(type, extra) {
        var evt = {
            timestamp: performance.now(),
            event_type: type,
            page_url: window.location.pathname,
            event_data: extra || {}
        };
        buffer.push(evt);
    }

    function flush() {
        if (buffer.length === 0) return;
        var toSend = buffer.splice(0, buffer.length);
        var methodSessionId = document.body.dataset.methodSessionId || '';
        try {
            navigator.sendBeacon('/api/track', JSON.stringify({
                events: toSend,
                method_session_id: methodSessionId || null
            }));
        } catch(e) {
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/track', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.send(JSON.stringify({
                events: toSend,
                method_session_id: methodSessionId || null
            }));
        }
    }

    function resetHesitation() {
        lastInteractionTime = performance.now();
        if (hesitationTimer) clearTimeout(hesitationTimer);
        hesitationTimer = setTimeout(function() {
            pushEvent('hesitation', {
                duration_ms: HESITATION_THRESHOLD,
                since_last_interaction: performance.now() - lastInteractionTime
            });
        }, HESITATION_THRESHOLD);
    }

    // Send session metadata
    function sendMeta() {
        var isIframe = false;
        try { isIframe = window !== window.parent; } catch(e) { isIframe = true; }

        var data = {
            screen_width: screen.width,
            screen_height: screen.height,
            language: navigator.language || '',
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
            is_iframe: isIframe
        };

        var xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/session_meta', true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.send(JSON.stringify(data));
    }

    // Event listeners
    document.addEventListener('click', function(e) {
        var info = getElementInfo(e.target);
        info.x = e.clientX;
        info.y = e.clientY;
        pushEvent('click', info);
        resetHesitation();
    }, true);

    document.addEventListener('change', function(e) {
        var info = getElementInfo(e.target);
        info.value = e.target.value || '';
        pushEvent('change', info);
        resetHesitation();
    }, true);

    var scrollTimeout = null;
    window.addEventListener('scroll', function() {
        if (scrollTimeout) return;
        scrollTimeout = setTimeout(function() {
            scrollTimeout = null;
            pushEvent('scroll', {
                scrollX: window.scrollX,
                scrollY: window.scrollY
            });
        }, 500);
    }, { passive: true });

    window.addEventListener('focus', function() {
        pushEvent('focus', {});
        resetHesitation();
    });

    window.addEventListener('blur', function() {
        pushEvent('blur', {});
    });

    document.addEventListener('visibilitychange', function() {
        pushEvent('visibility_change', { hidden: document.hidden });
    });

    window.addEventListener('resize', function() {
        pushEvent('resize', {
            width: window.innerWidth,
            height: window.innerHeight
        });
    });

    document.addEventListener('submit', function(e) {
        var info = getElementInfo(e.target);
        pushEvent('form_submit', info);
        flush();
    }, true);

    document.addEventListener('keypress', function(e) {
        var info = getElementInfo(e.target);
        pushEvent('keypress', info);
        resetHesitation();
    }, true);

    // Page load
    pushEvent('page_load', {
        url: window.location.href,
        referrer: document.referrer
    });

    // Flush on unload
    window.addEventListener('beforeunload', function() {
        pushEvent('page_unload', {
            time_on_page_ms: performance.now() - pageStartTime
        });
        flush();
    });

    // Periodic flush
    setInterval(flush, FLUSH_INTERVAL);

    // Init
    sendMeta();
    resetHesitation();
})();
