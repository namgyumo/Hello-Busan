/**
 * sse.js — SSE 실시간 갱신
 */
const SSE = (() => {
    let eventSource = null;
    let onComfortUpdate = null;
    let onHeatmapUpdate = null;

    function connect() {
        if (eventSource) eventSource.close();

        eventSource = new EventSource('/api/v1/events/stream');

        eventSource.addEventListener('comfort_update', (e) => {
            try {
                const data = JSON.parse(e.data);
                if (onComfortUpdate) onComfortUpdate(data);
            } catch (err) {
                console.warn('SSE comfort parse error:', err);
            }
        });

        eventSource.addEventListener('heatmap_update', (e) => {
            try {
                const data = JSON.parse(e.data);
                if (onHeatmapUpdate) onHeatmapUpdate(data);
            } catch (err) {
                console.warn('SSE heatmap parse error:', err);
            }
        });

        eventSource.addEventListener('heartbeat', () => {
            // keep-alive
        });

        eventSource.onerror = () => {
            console.warn('SSE 연결 끊김, 자동 재연결...');
        };
    }

    function disconnect() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
    }

    function on(event, callback) {
        if (event === 'comfort_update') onComfortUpdate = callback;
        if (event === 'heatmap_update') onHeatmapUpdate = callback;
    }

    return { connect, disconnect, on };
})();
