-- Migración para añadir precio en dólares y la tabla de configuraciones

-- Crear nueva tabla de settings
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR PRIMARY KEY,
    value VARCHAR NOT NULL
);

-- Insertar por defecto una cotización de dólar blue (ejemplo: 1450)
INSERT INTO settings (key, value) VALUES ('manual_exchange_rate', '1450') ON CONFLICT DO NOTHING;

-- Agregar la columna price_usd a la tabla products si no existe
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='products' and column_name='price_usd') THEN
        ALTER TABLE products ADD COLUMN price_usd NUMERIC(12, 2);
    END IF;
END $$;
