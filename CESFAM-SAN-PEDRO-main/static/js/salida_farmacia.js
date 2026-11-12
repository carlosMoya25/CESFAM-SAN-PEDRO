(() => {
    const origen = document.getElementById("id_origen");
    const lote = document.getElementById("id_lote");
    const resumen = document.getElementById("stock-salida-preview");
    const datos = document.getElementById("stocks-salida");
    if (!origen || !lote || !resumen || !datos) return;

    const stocks = JSON.parse(datos.textContent);

    function actualizarLotes() {
        const origenId = origen.value;
        const lotePrevio = lote.value;
        const disponibles = stocks.filter(stock => String(stock.origen_id) === origenId);
        lote.replaceChildren(new Option("Seleccione un lote con stock disponible", ""));
        for (const stock of disponibles) {
            lote.add(new Option(stock.etiqueta, stock.lote_id));
        }
        if (disponibles.some(stock => String(stock.lote_id) === lotePrevio)) {
            lote.value = lotePrevio;
        }
        actualizarResumen();
    }

    function actualizarResumen() {
        const stock = stocks.find(item =>
            String(item.origen_id) === origen.value && String(item.lote_id) === lote.value
        );
        resumen.textContent = stock
            ? `${stock.cantidad} ${stock.etiqueta.split("Stock: ")[1]} disponibles en esta ubicación.`
            : "No hay un lote disponible seleccionado para esta ubicación.";
    }

    origen.addEventListener("change", actualizarLotes);
    lote.addEventListener("change", actualizarResumen);
    actualizarLotes();
})();
