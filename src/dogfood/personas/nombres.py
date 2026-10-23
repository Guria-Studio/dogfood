"""Listas locales de nombres y apellidos por idioma (sin acentos en el slug, con acentos aquí)."""

PT_BR_NOMBRES = ["Miguel", "Arthur", "Heitor", "Theo", "Davi", "Gabriel", "Bernardo", "Samuel", "João", "Enzo", "Lucas", "Matheus", "Pedro", "Guilherme", "Rafael", "Gustavo", "Felipe", "Daniel", "Henrique", "Murilo", "Eduardo", "Leonardo", "Nicolas", "Caio", "Vinícius", "Bruno", "Thiago", "Diego", "Rodrigo", "Leandro", "Fábio", "Marcelo", "Ricardo", "André", "Carlos", "Paulo", "Sérgio", "Renato", "Fernando", "Alexandre", "Juliano", "Helena", "Alice", "Laura", "Maria", "Sophia", "Manuela", "Valentina", "Heloísa", "Isabella", "Luiza", "Júlia", "Lorena", "Lívia", "Beatriz", "Mariana", "Gabriela", "Larissa", "Camila", "Fernanda", "Amanda", "Bruna", "Letícia", "Patrícia", "Aline", "Renata", "Carolina", "Juliana", "Vanessa", "Priscila", "Tatiana", "Cláudia", "Adriana", "Daniela", "Débora", "Simone", "Roberta", "Elaine", "Cristiane", "Natália", "Bianca", "Rafaela", "Thaís", "Raquel", "Vitória", "Eduarda", "Yasmin", "Ana"]

PT_BR_APELLIDOS = ["Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves", "Pereira", "Lima", "Gomes", "Costa", "Ribeiro", "Martins", "Carvalho", "Almeida", "Lopes", "Soares", "Fernandes", "Vieira", "Barbosa", "Rocha", "Dias", "Nascimento", "Andrade", "Moreira", "Nunes", "Marques", "Machado", "Mendes", "Freitas", "Cardoso", "Ramos", "Gonçalves", "Santana", "Teixeira", "Araújo", "Moura", "Cavalcanti", "Monteiro", "Correia", "Campos", "Pinto", "Azevedo", "Batista", "Borges", "Brito", "Duarte", "Castro", "Farias", "Guimarães", "Melo", "Miranda", "Xavier", "Peixoto", "Rezende", "Siqueira", "Tavares", "Toledo", "Vasconcelos", "Medeiros", "Fonseca", "Coelho", "Cunha", "Barros", "Bezerra", "Sampaio", "Paiva", "Pires", "Prado", "Franco", "Leal", "Lacerda", "Macedo", "Magalhães", "Matos", "Neves", "Ramalho", "Salgado", "Sales", "Viana", "Zanetti", "Bastos", "Amaral", "Braga", "Cordeiro", "Domingues", "Esteves"]

ES_NOMBRES = ["Santiago", "Mateo", "Sebastián", "Matías", "Nicolás", "Alejandro", "Diego", "Samuel", "Benjamín", "Daniel", "Joaquín", "Lucas", "Tomás", "Emiliano", "Gabriel", "Andrés", "Felipe", "Camilo", "Juan", "Carlos", "Luis", "Jorge", "Pablo", "Javier", "Fernando", "Ricardo", "Eduardo", "Roberto", "Miguel", "Héctor", "Óscar", "Rafael", "Sergio", "Manuel", "Gustavo", "Hugo", "Iván", "Cristian", "Esteban", "Ignacio", "Mauricio", "Sofía", "Valentina", "Isabella", "Camila", "Valeria", "Mariana", "Gabriela", "Daniela", "Martina", "Lucía", "Victoria", "Ximena", "Renata", "Natalia", "Paula", "Andrea", "Carolina", "Fernanda", "Alejandra", "Claudia", "Patricia", "Verónica", "Mónica", "Laura", "Ana", "Marta", "Rosa", "Carmen", "Elena", "Silvia", "Beatriz", "Liliana", "Marcela", "Paola", "Diana", "Catalina", "Juliana", "Lorena", "Susana", "Teresa", "Adriana", "Rocío", "Pilar", "Gloria", "Inés", "Julieta"]

ES_APELLIDOS = ["García", "Rodríguez", "Martínez", "López", "González", "Hernández", "Pérez", "Sánchez", "Ramírez", "Torres", "Flores", "Rivera", "Gómez", "Díaz", "Reyes", "Morales", "Cruz", "Ortiz", "Gutiérrez", "Chávez", "Ramos", "Vargas", "Castillo", "Jiménez", "Moreno", "Romero", "Herrera", "Medina", "Aguilar", "Castro", "Vázquez", "Mendoza", "Fernández", "Rojas", "Salazar", "Silva", "Núñez", "Cabrera", "Ríos", "Guerrero", "Paredes", "Vega", "Campos", "Soto", "Delgado", "Peña", "Molina", "Ávila", "Cortés", "Navarro", "Domínguez", "Acosta", "Ibarra", "Lara", "Maldonado", "Fuentes", "Contreras", "Espinoza", "Valencia", "Cárdenas", "Arias", "Bravo", "Carrillo", "Montoya", "Restrepo", "Ospina", "Quintero", "Arango", "Zapata", "Henao", "Giraldo", "Londoño", "Villalobos", "Barrios", "Solís", "Santos", "Duarte", "Benítez", "Figueroa", "Escobar", "Pacheco", "Serrano", "Zamora", "Orozco", "Galindo", "Mejía"]

NOMBRES = {"pt-BR": PT_BR_NOMBRES, "es": ES_NOMBRES}
APELLIDOS = {"pt-BR": PT_BR_APELLIDOS, "es": ES_APELLIDOS}

# Rubros del objetivo y prefijos/sufijos de empresa por idioma.
RUBROS = ["farmacia", "pet shop", "cosmética", "café", "e-commerce", "agencia"]

EMPRESAS = {
    "pt-BR": {
        "farmacia": "Drogaria {a}",
        "pet shop": "Pet Shop {a}",
        "cosmética": "{a} Cosméticos",
        "café": "Café {a}",
        "e-commerce": "{a} Store",
        "agencia": "Agência {a}",
    },
    "es": {
        "farmacia": "Farmacia {a}",
        "pet shop": "Veterinaria y Pet Shop {a}",
        "cosmética": "Cosméticos {a}",
        "café": "Café {a}",
        "e-commerce": "Tienda {a}",
        "agencia": "Agencia {a}",
    },
}
