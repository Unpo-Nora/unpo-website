UPDATE products SET stock_quantity = 0 WHERE name ILIKE '%Mochila%';

UPDATE products 
SET images = '["/static/images/10300016.jpeg", "/static/images/10300016_1.jpeg"]'::jsonb 
WHERE sku = '10300016';

INSERT INTO products (sku, name, description, category_id, price_wholesale, stock_quantity, images, is_active, weight)
VALUES 
('10700084', 'VELADOR ESFERA CRISTAL 3D', 'LAMPARA VELADOR CREATIVA ESFERA CRISTAL 3D LED USB CHICA ELEFANTE O DIENTE DE LEON', 6, 7000.00, 12, '["/static/images/10700084.jpeg", "/static/images/10700084_1.jpeg", "/static/images/10700084_2.jpeg", "/static/images/10700084_3.jpeg"]'::jsonb, true, 0),
('10700085', 'REJILLA SILICONA', 'REJILLA SILICONA BAÑO COCINA PELOS BACHA RESIDUOS NEGRO GRIS ROJO VERDE', 3, 780.00, 101, '["/static/images/10700085.jpg", "/static/images/10700085_1.jpeg", "/static/images/10700085_2.jpeg", "/static/images/10700085_3.jpeg", "/static/images/10700085_4.jpeg", "/static/images/10700085_5.jpeg"]'::jsonb, true, 0)
ON CONFLICT (sku) DO UPDATE SET 
    stock_quantity = EXCLUDED.stock_quantity,
    images = EXCLUDED.images,
    price_wholesale = EXCLUDED.price_wholesale;
