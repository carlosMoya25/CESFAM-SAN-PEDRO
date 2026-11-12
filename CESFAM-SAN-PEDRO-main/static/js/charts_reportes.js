/*
 * Gráficos compartidos por los 4 paneles de reportes (vista general,
 * soporte TI, insumos y farmacia). Centralizar la configuración aquí
 * evita que cada panel dibuje sus gráficos "a su manera".
 */
(function () {
    "use strict";

    const PALETA = ["#087ea4", "#14a6a0", "#f59e0b", "#e11d48", "#2563eb", "#16a34a", "#64748b", "#9333ea"];

    function leerDatos(id) {
        const elemento = document.getElementById(id);
        if (!elemento) return null;
        try {
            return JSON.parse(elemento.textContent);
        } catch (error) {
            return null;
        }
    }

    function hayChart() {
        return typeof Chart !== "undefined";
    }

    window.ReportesCharts = {
        /** Dona a partir de un diccionario {etiqueta: total, ...} (ej. solicitudes por estado). */
        donut: function (canvasId, datosId) {
            const datos = leerDatos(datosId);
            const canvas = document.getElementById(canvasId);
            if (!datos || !canvas || !hayChart() || Object.keys(datos).length === 0) return;

            new Chart(canvas, {
                type: "doughnut",
                data: {
                    labels: Object.keys(datos),
                    datasets: [{
                        data: Object.values(datos),
                        backgroundColor: PALETA,
                        borderWidth: 0,
                    }],
                },
                options: {
                    cutout: "62%",
                    plugins: {
                        legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
                    },
                },
            });
        },

        /** Barras horizontales a partir de [{<campoEtiqueta>: ..., <campoValor>: ...}, ...]. */
        barrasHorizontales: function (canvasId, datosId, campoEtiqueta, campoValor) {
            const filas = (leerDatos(datosId) || []).filter(function (fila) {
                return fila[campoEtiqueta];
            });
            const canvas = document.getElementById(canvasId);
            if (!canvas || !hayChart() || filas.length === 0) return;

            new Chart(canvas, {
                type: "bar",
                data: {
                    labels: filas.map(function (fila) { return fila[campoEtiqueta]; }),
                    datasets: [{
                        data: filas.map(function (fila) { return fila[campoValor]; }),
                        backgroundColor: "#14a6a0",
                    }],
                },
                options: {
                    indexAxis: "y",
                    plugins: { legend: { display: false } },
                    scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
                },
            });
        },
    };
})();
