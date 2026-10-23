"""Rubros con catálogo, precios y ciclos verdaderos para el generador de ventas."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Producto:
    id: str
    sku: str
    ean: str
    nombre_pt: str
    nombre_es: str
    precio: float
    ciclo_min: float
    ciclo_max: float
    sigma_log: float
    durable: bool

    def nombre(self, idioma: str) -> str:
        return self.nombre_es if idioma.startswith("es") else self.nombre_pt


@dataclass(frozen=True)
class Perfil:
    nombre: str
    ciclo_min: int
    ciclo_max: int
    productos: tuple[Producto, ...]

    @property
    def proporcion_durables(self) -> float:
        return sum(p.durable for p in self.productos) / len(self.productos)


def digito_ean13(base12: str) -> str:
    suma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(base12))
    return str((10 - suma % 10) % 10)


def ean13_valido(ean: str) -> bool:
    return len(ean) == 13 and ean.isdigit() and digito_ean13(ean[:12]) == ean[12]


# (nombre pt-BR, nombre es, precio, durable)
_CATALOGOS: dict[str, tuple[int, int, list[tuple[str, str, float, bool]]]] = {
    "farmacia": (
        20,
        35,
        [
            ("Dipirona 500mg 20 comprimidos", "Dipirona 500mg 20 comprimidos", 12.90, False),
            ("Paracetamol 750mg 20 comprimidos", "Paracetamol 750mg 20 comprimidos", 9.50, False),
            ("Losartana 50mg 30 comprimidos", "Losartán 50mg 30 comprimidos", 18.70, False),
            ("Metformina 850mg 30 comprimidos", "Metformina 850mg 30 comprimidos", 14.20, False),
            ("Omeprazol 20mg 28 cápsulas", "Omeprazol 20mg 28 cápsulas", 21.40, False),
            ("Sinvastatina 20mg 30 comprimidos", "Simvastatina 20mg 30 comprimidos", 16.80, False),
            ("Vitamina D 2000UI 60 cápsulas", "Vitamina D 2000UI 60 cápsulas", 39.90, False),
            ("Protetor solar FPS 50 200ml", "Protector solar FPS 50 200ml", 54.90, False),
            ("Fralda infantil M 40 unidades", "Pañal infantil M 40 unidades", 49.90, False),
            ("Lenço umedecido 100 unidades", "Toallitas húmedas 100 unidades", 13.90, False),
            ("Soro fisiológico 500ml", "Suero fisiológico 500ml", 8.90, False),
            ("Escova dental macia", "Cepillo dental suave", 7.50, False),
            ("Creme dental 90g", "Pasta dental 90g", 6.90, False),
            ("Fio dental 50m", "Hilo dental 50m", 11.90, False),
            ("Álcool em gel 500ml", "Alcohol en gel 500ml", 15.90, False),
            ("Hidratante corporal 400ml", "Crema corporal 400ml", 29.90, False),
            ("Tiras de glicemia 50 unidades", "Tiras de glucemia 50 unidades", 79.90, False),
            ("Termômetro digital", "Termómetro digital", 24.90, True),
            ("Medidor de pressão de braço", "Tensiómetro de brazo", 189.90, True),
            ("Nebulizador ultrassônico", "Nebulizador ultrasónico", 159.90, True),
        ],
    ),
    "pet-shop": (
        25,
        40,
        [
            ("Ração cão adulto 15kg", "Alimento perro adulto 15kg", 189.90, False),
            ("Ração gato castrado 10kg", "Alimento gato castrado 10kg", 169.90, False),
            ("Ração filhote 3kg", "Alimento cachorro 3kg", 59.90, False),
            ("Sachê gato 85g caixa 12", "Sobre gato 85g caja 12", 34.90, False),
            ("Petisco bifinho 500g", "Premio bifecito 500g", 29.90, False),
            ("Areia sanitária 4kg", "Arena sanitaria 4kg", 24.90, False),
            ("Tapete higiênico 30 unidades", "Paño higiénico 30 unidades", 54.90, False),
            ("Antipulgas cão 10-20kg", "Antipulgas perro 10-20kg", 89.90, False),
            ("Vermífugo 4 comprimidos", "Antiparasitario 4 comprimidos", 39.90, False),
            ("Shampoo neutro pet 500ml", "Champú neutro mascota 500ml", 22.90, False),
            ("Osso de couro 3 unidades", "Hueso de cuero 3 unidades", 19.90, False),
            ("Ração pássaro 1kg", "Alimento pájaro 1kg", 18.90, False),
            ("Ração peixe 100g", "Alimento peces 100g", 15.90, False),
            ("Feno para roedor 500g", "Heno para roedor 500g", 21.90, False),
            ("Sabonete pet 90g", "Jabón mascota 90g", 9.90, False),
            ("Patê cão 280g", "Paté perro 280g", 12.90, False),
            ("Coleira ajustável", "Collar ajustable", 39.90, True),
            ("Cama pet média", "Cama mascota mediana", 129.90, True),
            ("Comedouro inox", "Comedero acero inoxidable", 34.90, True),
            ("Caixa de transporte", "Transportadora", 149.90, True),
        ],
    ),
    "cosmetica": (
        30,
        60,
        [
            ("Shampoo hidratante 300ml", "Champú hidratante 300ml", 32.90, False),
            ("Condicionador 300ml", "Acondicionador 300ml", 34.90, False),
            ("Máscara capilar 250g", "Mascarilla capilar 250g", 45.90, False),
            ("Sérum vitamina C 30ml", "Sérum vitamina C 30ml", 89.90, False),
            ("Hidratante facial 50g", "Crema facial 50g", 69.90, False),
            ("Água micelar 200ml", "Agua micelar 200ml", 39.90, False),
            ("Base líquida 30ml", "Base líquida 30ml", 79.90, False),
            ("Máscara de cílios", "Máscara de pestañas", 49.90, False),
            ("Batom matte", "Labial mate", 29.90, False),
            ("Esmalte 8ml", "Esmalte de uñas 8ml", 8.90, False),
            ("Removedor de esmalte 100ml", "Quitaesmalte 100ml", 7.90, False),
            ("Desodorante roll-on 50ml", "Desodorante roll-on 50ml", 16.90, False),
            ("Perfume 100ml", "Perfume 100ml", 199.90, False),
            ("Óleo corporal 200ml", "Aceite corporal 200ml", 54.90, False),
            ("Sabonete facial 150ml", "Jabón facial 150ml", 36.90, False),
            ("Tônico facial 200ml", "Tónico facial 200ml", 42.90, False),
            ("Protetor labial", "Protector labial", 14.90, False),
            ("Secador de cabelo", "Secador de pelo", 249.90, True),
            ("Chapinha de cerâmica", "Plancha de cerámica", 189.90, True),
            ("Kit de pincéis", "Set de brochas", 99.90, True),
        ],
    ),
    "cafe": (
        10,
        20,
        [
            ("Café especial em grãos 250g", "Café de especialidad en grano 250g", 42.90, False),
            ("Café especial moído 250g", "Café de especialidad molido 250g", 39.90, False),
            ("Café torra escura 500g", "Café tueste oscuro 500g", 34.90, False),
            ("Café descafeinado 250g", "Café descafeinado 250g", 44.90, False),
            ("Café em cápsulas 10 unidades", "Café en cápsulas 10 unidades", 24.90, False),
            ("Café gourmet 1kg", "Café gourmet 1kg", 99.90, False),
            ("Blend da casa 500g", "Blend de la casa 500g", 49.90, False),
            ("Café orgânico 250g", "Café orgánico 250g", 46.90, False),
            ("Cold brew 1L", "Cold brew 1L", 29.90, False),
            ("Filtro de papel 103 30 unidades", "Filtro de papel 103 30 unidades", 8.90, False),
            ("Leite vegetal 1L", "Leche vegetal 1L", 16.90, False),
            ("Açúcar demerara 1kg", "Azúcar mascabo 1kg", 12.90, False),
            ("Chocolate em pó 200g", "Chocolate en polvo 200g", 19.90, False),
            ("Biscoito amanteigado 200g", "Galletas de mantequilla 200g", 14.90, False),
            ("Chá mate 250g", "Yerba mate 250g", 18.90, False),
            ("Xarope de baunilha 250ml", "Jarabe de vainilla 250ml", 32.90, False),
            ("Moedor manual", "Molinillo manual", 189.90, True),
            ("Prensa francesa 600ml", "Prensa francesa 600ml", 119.90, True),
            ("Cafeteira italiana", "Cafetera italiana", 139.90, True),
            ("Balança de precisão", "Balanza de precisión", 89.90, True),
        ],
    ),
    "e-commerce": (
        30,
        90,
        [
            ("Papel higiênico 12 rolos", "Papel higiénico 12 rollos", 24.90, False),
            ("Sabão líquido 3L", "Detergente líquido 3L", 49.90, False),
            ("Amaciante 2L", "Suavizante 2L", 22.90, False),
            ("Detergente 500ml caixa 6", "Lavavajillas 500ml caja 6", 17.90, False),
            ("Saco de lixo 50 unidades", "Bolsas de basura 50 unidades", 19.90, False),
            ("Papel toalha 2 rolos", "Papel de cocina 2 rollos", 9.90, False),
            ("Pilhas AA 8 unidades", "Pilas AA 8 unidades", 29.90, False),
            ("Lâmina de barbear 4 unidades", "Hojas de afeitar 4 unidades", 44.90, False),
            ("Cápsula de lava-louças 30", "Pastillas lavavajillas 30", 59.90, False),
            ("Refil de filtro de água", "Repuesto de filtro de agua", 69.90, False),
            ("Ração gato 3kg", "Alimento gato 3kg", 54.90, False),
            ("Whey protein 900g", "Proteína whey 900g", 129.90, False),
            ("Café em cápsulas 50 unidades", "Café en cápsulas 50 unidades", 99.90, False),
            ("Lenço de papel 6 caixas", "Pañuelos de papel 6 cajas", 21.90, False),
            ("Multiuso 500ml caixa 3", "Limpiador multiuso 500ml caja 3", 18.90, False),
            ("Esponja 10 unidades", "Esponjas 10 unidades", 12.90, False),
            ("Fone de ouvido bluetooth", "Auriculares bluetooth", 199.90, True),
            ("Carregador USB-C", "Cargador USB-C", 79.90, True),
            ("Garrafa térmica 1L", "Termo 1L", 89.90, True),
            ("Mochila notebook", "Mochila para notebook", 159.90, True),
            ("Luminária LED de mesa", "Lámpara LED de escritorio", 119.90, True),
        ],
    ),
    "agencia": (
        25,
        35,
        [
            ("Gestão de redes sociais mensal", "Gestión de redes sociales mensual", 1500.0, False),
            ("Pacote 12 posts", "Paquete 12 publicaciones", 600.0, False),
            ("Gestão de tráfego pago", "Gestión de tráfico pago", 1200.0, False),
            ("Relatório de desempenho", "Informe de desempeño", 300.0, False),
            ("Newsletter mensal", "Newsletter mensual", 450.0, False),
            ("Artigo de blog SEO", "Artículo de blog SEO", 250.0, False),
            ("Pacote 4 reels", "Paquete 4 reels", 800.0, False),
            ("Sessão de fotos de produto", "Sesión de fotos de producto", 900.0, False),
            ("Manutenção de site", "Mantenimiento de sitio web", 350.0, False),
            ("Hospedagem mensal", "Hosting mensual", 89.0, False),
            ("Consultoria estratégica 2h", "Consultoría estratégica 2h", 500.0, False),
            ("Campanha de e-mail", "Campaña de e-mail", 400.0, False),
            ("Gestão de Google Meu Negócio", "Gestión de Google Mi Negocio", 250.0, False),
            ("Moderação de comentários", "Moderación de comentarios", 300.0, False),
            ("Pacote de stories", "Paquete de historias", 350.0, False),
            ("Anúncio no LinkedIn", "Anuncio en LinkedIn", 700.0, False),
            ("Criação de logotipo", "Diseño de logotipo", 1800.0, True),
            ("Site institucional", "Sitio institucional", 4500.0, True),
            ("Manual de marca", "Manual de marca", 2500.0, True),
            ("Loja virtual", "Tienda virtual", 6000.0, True),
        ],
    ),
}


def _armar(i: int, nombre: str, lo: int, hi: int, items: list) -> Perfil:
    # Ciclo y ruido por producto: fijos para el catálogo (semilla = índice del rubro).
    rng = np.random.default_rng(1000 + i)
    productos = []
    for j, (pt, es, precio, durable) in enumerate(items, start=1):
        centro = rng.uniform(lo, hi)
        sigma = round(float(rng.uniform(0.15, 0.4)), 3)
        base = f"789{i:02d}{j:07d}"
        productos.append(
            Producto(
                id=f"{nombre}-{j:03d}",
                sku=f"{nombre.replace('-', '')[:3].upper()}-{j:04d}",
                ean=base + digito_ean13(base),
                nombre_pt=pt,
                nombre_es=es,
                precio=precio,
                ciclo_min=round(max(lo, centro * 0.85), 1),
                ciclo_max=round(min(hi, centro * 1.15), 1),
                sigma_log=sigma,
                durable=durable,
            )
        )
    return Perfil(nombre, lo, hi, tuple(productos))


PERFILES: dict[str, Perfil] = {
    nombre: _armar(i, nombre, lo, hi, items)
    for i, (nombre, (lo, hi, items)) in enumerate(_CATALOGOS.items(), start=1)
}
