"""SEPE Contrat@ official code tables.

Source: https://www.sepe.es/DocumComunicacto/xml/14/
XSD: EsquemaContratos50.xsd (version 5.0)

These tables contain the official code values used in SEPE Contrat@ XML
communication. Each table maps code -> description.

Reference: Ayuda XML -> Ultima version -> Tablas de codigos
"""

from __future__ import annotations

# ============================================================================
# TNWTPCOM - Tipos de Contrato (Contract Types)
# ============================================================================
CONTRACT_TYPES: dict[str, str] = {
    # Verified against XSD EsquemaContratos50.xsd (45 elements, 2025-06-14)
    "100": "Indefinido ordinario a tiempo completo",
    "130": "Indefinido minusvalido a tiempo completo",
    "150": "Indefinido a tiempo completo con bonificacion",
    "200": "Indefinido ordinario a tiempo parcial",
    "230": "Indefinido minusvalido a tiempo parcial",
    "250": "Indefinido a tiempo parcial con bonificacion",
    "300": "Fijo discontinuo",
    "330": "Minusvalido fijo discontinuo",
    "350": "Fijo discontinuo con bonificacion",
    "401": "Obra o servicio TC [DEPRECADO RDL 32/2021 desde 31/03/2022]",
    "402": "Circunstancias de la produccion a tiempo completo",
    "403": "Insercion a tiempo completo",
    "404": "Personal investigador predoctoral en formacion",
    "405": "Vinculado a programas de politicas activas de empleo TC",
    "406": "Duracion determinada financiado con fondos europeos TC",
    "407": "Contrato Artistico de duracion determinada TC",
    "409": "Ley Organica de Universidades 6/2001 TC",
    "410": "Sustitucion a tiempo completo",
    "412": "Contrato acceso personal investigador doctor TC",
    "413": "Deportistas profesionales a tiempo completo",
    "420": "Formativo para obtencion practica profesional TC",
    "421": "Formacion en alternancia TC",
    "430": "Temporal minusvalido a tiempo completo",
    "441": "Relevo a tiempo completo",
    "450": "Exclusion social a tiempo completo",
    "452": "Temporal a TC bonificado para empresas de insercion",
    "501": "Obra o servicio TP [DEPRECADO RDL 32/2021 desde 31/03/2022]",
    "502": "Circunstancias de la produccion a tiempo parcial",
    "503": "Insercion a tiempo parcial",
    "505": "Vinculado a programas de politicas activas de empleo TP",
    "506": "Duracion determinada financiado con fondos europeos TP",
    "507": "Contrato Artistico de duracion determinada TP",
    "509": "Ley Organica de Universidades 6/2001 TP",
    "510": "Sustitucion a tiempo parcial",
    "513": "Deportistas profesionales a tiempo parcial",
    "520": "Formativo para obtencion practica profesional TP",
    "521": "Formacion en alternancia a tiempo parcial",
    "530": "Temporal minusvalido a tiempo parcial",
    "540": "Jubilacion parcial",
    "541": "Relevo a tiempo parcial",
    "550": "Exclusion social a tiempo parcial",
    "552": "Temporal a TP bonificado para empresas de insercion",
    "970": "Adscripcion en colaboracion social",
    "980": "Jubilacion especial a los 64 anos",
    "990": "Otros contratos",
}

DEPRECATED_CONTRACT_CODES: set[str] = {"401", "501"}

# ============================================================================
# TCHRGCOT - Regimenes de Cotizacion (Social Security Regimes)
# ============================================================================
COTIZACION_REGIMES: dict[str, str] = {
    "0111": "Regimen General",
    "0112": "Regimen General (Empleados de Hogar)",
    "0132": "Regimen General (Trabajadores Cuentas Propias Mineros Carbon)",
    "0162": "R.E. Trabajadores del Mar",
    "0163": "R.E. Trabajadores del Mar (Cuentas Propias)",
    "0511": "Regimen Especial Agrario (Sistema Especial)",
    "0521": "R.E. de los Trabajadores Autonomos (RETA)",
    "0522": "RETA (Sistema Especial para Trabajadores por Cuenta Propia Agrarios)",
    "0523": "RETA (Sistema Especial de Trabajadores por Cuenta Propia del Mar)",
    "0613": "Mutualidad de Funcionarios de la Administracion de Justicia (MUFACE)",
    "0640": "Clases Pasivas del Estado",
    "0722": "R.E. de Empleadas de Hogar (derogado, integrado en RG)",
}

# ============================================================================
# STDIDETC - Tipos de Documento de Identidad (Document Types)
# ============================================================================
DOCUMENT_TYPES: dict[str, str] = {
    "D": "DNI (Documento Nacional de Identidad)",
    "E": "NIE (Numero de Identidad de Extranjero)",
    "P": "Pasaporte",
    "C": "Certificado de ciudadano de la Union Europea",
    "X": "Permiso de residencia temporal",
    "R": "Certificado de registro de ciudadano de la UE",
    "T": "Tarjeta de identidad de extranjero",
    "H": "Documento de identidad pais de origen (UE)",
    "I": "Documento de identidad pais de origen (no UE)",
    "N": "Numero de identificacion fiscal (NIF)",
    "W": "Certificado de registro de ciudadano de la UE (familiar)",
}

# ============================================================================
# TCMCSEXO - Sexo (Gender)
# ============================================================================
GENDER_CODES: dict[str, str] = {
    "1": "Hombre (Varon)",
    "2": "Mujer",
    "6": "No consta",
}

# ============================================================================
# TBONVFOR - Niveles Formativos (Education Levels)
# ============================================================================
EDUCATION_LEVELS: dict[str, str] = {
    "10": "No sabe leer ni escribir",
    "11": "Sin estudios (sin titulacion)",
    "12": "Primaria (EGB, ESO completa)",
    "20": "Bachillerato elemental / Graduado escolar / EGB completa",
    "21": "FP Grado Medio (Tecnico)",
    "22": "Bachillerato superior / BUP / COU",
    "30": "FP Grado Superior (Tecnico Superior)",
    "31": "FP Grado Medio (Tecnico)",
    "33": "Certificado de Profesionalidad",
    "40": "Diplomado universitario / Arquitecto Tecnico / Ingeniero Tecnico",
    "41": "Diplomado universitario",
    "42": "Estudios universitarios incompletos",
    "43": "Ingeniero Tecnico",
    "44": "Arquitecto Tecnico",
    "50": "Licenciado universitario / Arquitecto / Ingeniero",
    "51": "Licenciado universitario",
    "52": "Ingeniero",
    "53": "Arquitecto",
    "54": "Ingeniero de Montes / Industrial / Caminos",
    "55": "Doctorado universitario",
    "57": "Grado universitario",
    "58": "Master universitario",
    "59": "Estudios propios universitarios",
    "60": "Titulo propio universitario",
}

# ============================================================================
# TAICLAOC - Ocupaciones (Occupations) - CNO-11 codes
# Key: 4-digit code, padded to 8 in XML (4 blanks right)
# ============================================================================
OCCUPATIONS: dict[str, str] = {
    "0101": "Oficiales de las fuerzas armadas",
    "0110": "Otros oficiales de las fuerzas armadas",
    "0201": "Miembros del poder ejecutivo y del poder legislativo",
    "0210": "Directores de oficina y servicios administrativos",
    "0220": "Directores y gerentes de empresas",
    "0230": "Gerentes de comercios al por menor",
    "0301": "Profesionales de la salud (medicos, enfermeros)",
    "0302": "Profesionales de la educacion (profesores)",
    "0303": "Profesionales de las ciencias fisicas, quimicas y matematicas",
    "0304": "Profesionales de la informatica",
    "0310": "Otros profesionales cientificos e intelectuales",
    "0401": "Profesionales de apoyo a la salud",
    "0402": "Profesionales de apoyo a la educacion",
    "0410": "Otros profesionales de apoyo (tecnicos)",
    "0501": "Empleados de oficina (administrativos)",
    "0502": "Empleados de atencion al publico",
    "0510": "Otros empleados de oficina y operadores",
    "0601": "Trabajadores de los servicios de restauracion",
    "0602": "Trabajadores de los servicios de proteccion",
    "0603": "Vendedores de comercios",
    "0610": "Otros trabajadores de servicios y comerciantes",
    "0701": "Agricultores y trabajadores cualificados",
    "0702": "Trabajadores cualificados de la pesca y la acuicultura",
    "0703": "Trabajadores cualificados de la construccion",
    "0704": "Trabajadores cualificados de la metalurgia y manufactura",
    "0710": "Otros artesanos y trabajadores cualificados",
    "0801": "Operadores de maquinaria fija",
    "0802": "Conductores de vehiculos y operadores de maquinaria movil",
    "0810": "Otros operadores de instalaciones y maquinaria",
    "0901": "Peones agrarios, forestales y de la pesca",
    "0902": "Peones de la construccion",
    "0903": "Peones de la industria manufacturera",
    "0910": "Otros peones (transporte, carga y descarga)",
    "0000": "No determinada / Sin clasificar",
}

# ============================================================================
# TELCOLBO - Colectivos de Bonificacion (Bonus Collectives)
# ============================================================================
BONUS_COLLECTIVES: dict[str, str] = {
    "001": "Mujeres (contratos indefinidos a TC)",
    "002": "Mayores de 45 anos",
    "003": "Parados de larga duracion",
    "004": "Minusvalidos",
    "005": "Trabajadores de ETT contratados indefinidamente",
    "006": "Victimas de violencia de genero o domesticos",
    "007": "Personas en situacion de exclusion social",
    "008": "Jovenes desempleados menores de 30 anos (RDL 4/2013)",
    "009": "Jovenes desempleados menores de 30 anos con parodia larga (RDL 4/2013)",
    "010": "Personas desempleadas de larga duracion mayores de 45 (RDL 4/2013)",
    "011": "Personas desempleadas beneficiarias del PAE (RDL 4/2013)",
    "012": "Personas desempleadas de larga duracion de entre 30 y 45 anos",
    "013": "Personas con discapacidad de centros especiales de empleo",
    "014": "Personas con discapacidad de enclaves laborales",
    "015": "Personas con discapacidad (contrato de apoyo)",
    "016": "Jovenes inscritos en Garantia Juvenil (RDL 8/2014)",
    "017": "Parados de larga duracion mayores de 45 (RDL 4/2013)",
    "018": "Personas beneficiarias del PAE (RDL 3/2014)",
    "019": "Garantia Juvenil (RDL 8/2014)",
    "020": "Personas desempleadas inscritas en oficina empleo (RDL 1/2015)",
    "021": "Personas con discapacidad >= 33% (DA20 ET)",
    "022": "Personas con discapacidad >= 33% (DA20 ET)",
    "124": "Beneficiarios de prestaciones por desempleo de nivel contributivo",
    "125": "Beneficiarios de prestaciones por desempleo de nivel asistencial",
    "126": "Beneficiarios del programa de activacion para el empleo (PAE)",
}

# ============================================================================
# TEJINDIS - Indicador de Discapacidad (Disability Indicator)
# ============================================================================
DISABILITY_INDICATORS: dict[str, str] = {
    "S": "Si, persona con discapacidad",
    "C": "Centro especial de empleo (minusvalido)",
    "E": "Enclave laboral - grado de discapacidad >= 33% y < 65%",
    "F": "Enclave laboral - grado de discapacidad >= 65%",
    "G": "Enclave laboral - persona con enfermedad mental",
    "N": "No",
}

# ============================================================================
# TEQPTIEM - Periodo de Tiempo (Time Period for Partial Contracts)
# ============================================================================
TIME_PERIODS: dict[str, str] = {
    "D": "Diario",
    "S": "Semanal",
    "Q": "Quincenal",
    "M": "Mensual",
    "A": "Anual",
}

# ============================================================================
# TEIINTER - Causas de Sustitucion (Substitution Causes)
# ============================================================================
SUBSTITUTION_CAUSES: dict[str, str] = {
    "01": "Incapacidad temporal (baja medica)",
    "02": "Maternidad",
    "03": "Paternidad",
    "04": "Riesgo durante el embarazo",
    "05": "Riesgo durante la lactancia natural",
    "06": "Descanso por maternidad",
    "07": "Excedencia por cuidado de hijos",
    "08": "Excedencia por cuidado de familiares",
    "09": "Vacaciones",
    "10": "Reserva del puesto de trabajo (violencia genero)",
    "11": "Incapacidad permanente",
    "12": "Otras causas de sustitucion",
}

# ============================================================================
# TETPGMEM - Programas de Empleo (Employment Programs)
# ============================================================================
EMPLOYMENT_PROGRAMS: dict[str, str] = {
    "1": "Fomento de empleo agrario",
    "2": "Insercion en corporacion local",
    "3": "Escuela taller / Casa de oficios / Taller de empleo",
    "4": "Programas europeos",
    "5": "Colaboracion con ONGs",
    "6": "Plan de empleo de la D.G. del INEM",
    "7": "Ayuntamientos (Plan APRO)",
    "8": "Plan de empleojuvenil",
    "9": "Otros programas de empleo",
    "10": "Programas de cooperacion y desarrollo",
    "11": "Programas de orientacion profesional",
    "12": "Interes social en corporacion local",
    "13": "Promocion de empleo autonomo",
    "14": "Empleo publico en corporaciones locales",
    "15": "Insercion sociolaboral personas con discapacidad",
    "16": "Servicios de empleo de las CCAA",
}

# ============================================================================
# THITIACA - Titulaciones Academicas (Academic Qualifications)
# ============================================================================
ACADEMIC_QUALIFICATIONS: dict[str, str] = {
    "000000000000": "Sin titulacion",
    "100000000000": "Bachillerato",
    "110000000000": "Bachillerato (LOE)",
    "120000000000": "COU",
    "200000000000": "FP Grado Medio",
    "210000000000": "Tecnico (FP Grado Medio)",
    "300000000000": "FP Grado Superior",
    "310000000000": "Tecnico Superior (FP Grado Superior)",
    "400000000000": "Diplomado",
    "410000000000": "Diplomado (Universitario)",
    "500000000000": "Licenciado",
    "510000000000": "Licenciado (Universitario)",
    "520000000000": "Ingeniero",
    "530000000000": "Arquitecto",
    "600000000000": "Doctor",
    "610000000000": "Doctor (Universitario)",
    "700000000000": "Master Oficial",
    "710000000000": "Master Universitario",
}

# ============================================================================
# THYDISLE - Otras Disposiciones Legales (Other Legal Provisions)
# ============================================================================
LEGAL_PROVISIONS: dict[str, str] = {
    "1": "Mayores de 52 anos (indefinidos)",
    "2": "Contrato para mayores de 52 anos (temporal)",
}

# ============================================================================
# TCGPROVI - Codigos de Provincia (Province Codes) - INE official
# ============================================================================
PROVINCE_CODES: dict[str, str] = {
    "01": "Araba/Alava",
    "02": "Albacete",
    "03": "Alicante/Alacant",
    "04": "Almeria",
    "05": "Avila",
    "06": "Badajoz",
    "07": "Illes Balears",
    "08": "Barcelona",
    "09": "Burgos",
    "10": "Caceres",
    "11": "Cadiz",
    "12": "Castellon/Castello",
    "13": "Ciudad Real",
    "14": "Cordoba",
    "15": "A Coruna",
    "16": "Cuenca",
    "17": "Girona",
    "18": "Granada",
    "19": "Guadalajara",
    "20": "Gipuzkoa",
    "21": "Huelva",
    "22": "Huesca",
    "23": "Jaen",
    "24": "Leon",
    "25": "Lleida",
    "26": "La Rioja",
    "27": "Lugo",
    "28": "Madrid",
    "29": "Malaga",
    "30": "Murcia",
    "31": "Navarra",
    "32": "Ourense",
    "33": "Asturias",
    "34": "Palencia",
    "35": "Las Palmas",
    "36": "Pontevedra",
    "37": "Salamanca",
    "38": "Santa Cruz de Tenerife",
    "39": "Cantabria",
    "40": "Segovia",
    "41": "Sevilla",
    "42": "Soria",
    "43": "Tarragona",
    "44": "Teruel",
    "45": "Toledo",
    "46": "Valencia/Valencia",
    "47": "Valladolid",
    "48": "Bizkaia",
    "49": "Zamora",
    "50": "Zaragoza",
    "51": "Ceuta",
    "52": "Melilla",
}

# ============================================================================
# TBXCPAIS - Paises (Countries) - ISO 3166 numeric codes
# Key: 3-digit code
# ============================================================================
COUNTRY_CODES: dict[str, str] = {
    "724": "Espana",
    "036": "Australia",
    "040": "Austria",
    "056": "Belgica",
    "100": "Bulgaria",
    "124": "Canada",
    "152": "Chile",
    "156": "China",
    "191": "Croacia",
    "203": "Republica Checa",
    "208": "Dinamarca",
    "233": "Estonia",
    "246": "Finlandia",
    "250": "Francia",
    "276": "Alemania",
    "300": "Grecia",
    "348": "Hungria",
    "352": "Islandia",
    "372": "Irlanda",
    "380": "Italia",
    "392": "Japon",
    "528": "Paises Bajos",
    "578": "Noruega",
    "616": "Polonia",
    "620": "Portugal",
    "642": "Rumania",
    "643": "Rusia",
    "674": "San Marino",
    "688": "Serbia",
    "703": "Eslovaquia",
    "705": "Eslovenia",
    "752": "Suecia",
    "756": "Suiza",
    "826": "Reino Unido",
    "840": "Estados Unidos",
}

# ============================================================================
# TEYTRELE - Tipos de Trabajador de Relevo (Relief Worker Types)
# ============================================================================
RELIEF_WORKER_TYPES: dict[str, str] = {
    "1": "Trabajador desempleado inscrito como demandante de empleo",
    "2": "Trabajador con contrato suspendido o jornada reducida",
}

# ============================================================================
# TFGGRCOT - Grupos de Cotizacion (Social Security Contribution Groups)
# ============================================================================
CONTRIBUTION_GROUPS: dict[str, str] = {
    "01": "Ingenieros y Licenciados",
    "02": "Ingenieros Tecnicos, Peritos y Ayudantes Titulados",
    "03": "Jefes Administrativos y de Taller",
    "04": "Ayudantes no Titulados",
    "05": "Oficiales Administrativos",
    "06": "Subalternos",
    "07": "Auxiliares Administrativos",
    "08": "Oficiales de 1a",
    "09": "Oficiales de 2a",
    "10": "Oficiales de 3a y Especialistas",
    "11": "Peones",
    "12": "Trabajadores menores de 18 anos",
    "13": "Const. Grupos 1-7 (personal cualificado)",
    "14": "Const. Grupos 8-10 (personal especializado)",
    "15": "Const. Grupos 11-12 (personal no cualificado)",
    "16": "Aprendices y menores de 18 anos en formacion",
}

# ============================================================================
# TXREADEC - Acogida a Reales Decretos
# ============================================================================
ROYAL_DECREE_ADHERENCE: dict[str, str] = {
    "1": "Si, se acoge al RD",
    "2": "No, no se acoge al RD",
}

# ============================================================================
# TXORDMIN - Ordenes Ministeriales
# ============================================================================
MINISTERIAL_ORDERS: dict[str, str] = {
    "1": "Orden Ministerial 1",
    "2": "Orden Ministerial 2",
    "3": "Orden Ministerial 3",
    "4": "Orden Ministerial 4",
}

# ============================================================================
# TESCETCO - Escuelas Taller / Casa de Oficios / Talleres de Empleo
# ============================================================================
WORKSHOP_SCHOOL_CODES: dict[str, str] = {
    "T01": "Escuela Taller",
    "T02": "Escuela Taller (contrato indefinido)",
    "O01": "Casa de Oficios",
    "O02": "Casa de Oficios (contrato indefinido)",
    "E01": "Taller de Empleo",
    "E02": "Taller de Empleo (contrato indefinido)",
    "F01": "Programa de Formacion y Empleo",
    "F02": "Programa de Formacion y Empleo (contrato indefinido)",
}

# ============================================================================
# TEWEINVE - Tipo de Empleador Investigador
# ============================================================================
RESEARCH_EMPLOYER_TYPES: dict[str, str] = {
    "1": "Organismo publico de investigacion",
    "2": "Universidad publica",
    "3": "Universidad publica / Organismo publico (Ley 14/2011)",
    "4": "Universidad privada (Ley 14/2011)",
    "5": "Entidad sin animo de lucro (Ley 14/2011)",
    "6": "Centro de I+D privado (Ley 14/2011)",
    "7": "Organismo publico de investigacion (Ley 14/2011)",
    "8": "Entidad publica (Ley 14/2011)",
    "9": "Empresa (Ley 14/2011)",
}

# ============================================================================
# TEXTINVE - Tipo de Trabajador Investigador
# ============================================================================
RESEARCH_WORKER_TYPES: dict[str, str] = {
    "1": "Doctor",
    "2": "Titulado superior",
    "3": "Personal de apoyo",
    "4": "Personal investigador predoctoral",
    "5": "Investigador doctor",
    "6": "Tecnico de apoyo a la investigacion",
}

# ============================================================================
# TEUECCLL - Entidades Colaboradoras (Corporaciones Locales)
# ============================================================================
LOCAL_CORP_ENTITIES: dict[str, str] = {
    "01": "Ayuntamiento",
    "02": "Diputacion Provincial",
    "03": "Comunidad Autonoma (organismo auton)",
    "04": "Mancomunidad de Municipios",
    "05": "Comarca",
    "06": "Entidad municipal territorial menor",
    "07": "Area metropolitana",
    "08": "Consorcio",
    "09": "Otra entidad local",
}

# ============================================================================
# TEVACTCL - Codigos de Actuacion (Action Codes)
# ============================================================================
ACTION_CODES: dict[str, str] = {
    "1": "Alcantarillado y saneamiento",
    "2": "Construccion y reparacion de edificios",
    "3": "Conservacion y mantenimiento de vias",
    "4": "Instalacion y mantenimiento de jardines",
    "5": "Limpieza de vias publicas y edificios",
    "6": "Recogida, tratamiento y eliminacion de basuras",
    "7": "Suministro de aguas",
    "8": "Otras actuaciones",
    "9": "Obras de infraestructura",
}

# ============================================================================
# TERFIRCB - Tipo de Firma de la Copia Basica
# ============================================================================
BASIC_COPY_SIGNATURE_TYPES: dict[str, str] = {
    "1": "Firma electronica",
    "2": "Firma mecanica",
    "3": "No firmada",
}

# ============================================================================
# TQOCOLRE - Colectivos de Reduccion de Cuotas
# ============================================================================
FEE_REDUCTION_COLLECTIVES: dict[str, str] = {
    "08": "Jovenes desempleados menores de 30 anos (RDL 4/2013)",
    "09": "Jovenes desempleados menores de 30 con parodia larga",
    "10": "Personas desempleadas de larga duracion mayores de 45",
    "11": "Personas desempleadas beneficiarias del PAE",
    "12": "Personas desempleadas de larga duracion entre 30 y 45",
    "16": "Jovenes inscritos en Garantia Juvenil",
    "17": "Parados de larga duracion mayores de 45",
    "18": "Personas beneficiarias del PAE (RDL 3/2014)",
    "19": "Garantia Juvenil (RDL 8/2014)",
    "20": "Personas desempleadas inscritas en oficina (RDL 1/2015)",
    "21": "Personas con discapacidad >= 33% (DA20 ET) - formacion",
    "22": "Personas con discapacidad >= 33% (DA20 ET) - practicas",
}

# ============================================================================
# TRWCOLDF - Colectivos de Deduccion Fiscal (RDL 3/2012)
# ============================================================================
TAX_DEDUCTION_COLLECTIVES: dict[str, str] = {
    "1": "Empresas con menos de 50 trabajadores",
    "2": "Empresas de 50 o mas trabajadores",
    "3": "Microempresas y empresarios autonomos",
    "4": "Primer contrato joven menor de 30",
    "5": "Mantenimiento de empleo (empleado indefinido)",
}

# ============================================================================
# TEOCOLDE - Colectivos de Fomento Contratacion Indefinida (derogado 2012)
# ============================================================================
INDEFINITE_PROMOTION_COLLECTIVES: dict[str, str] = {
    "1": "Mujeres (sectores con baja representacion)",
    "2": "Mayores de 45 anos",
    "3": "Parados de larga duracion",
    "4": "Minusvalidos",
    "5": "Victimas de violencia de genero o domesticos",
    "6": "Personas en situacion de exclusion social",
}

# ============================================================================
# THPCOLFO - Colectivos de Edad en Formacion
# ============================================================================
TRAINING_AGE_COLLECTIVES: dict[str, str] = {
    "1": "Persona con discapacidad (sin limite de edad)",
    "2": "Victima de violencia de genero o domesticos (sin limite)",
    "3": "Victima de trata o trafico de seres humanos (sin limite)",
    "4": "Excluido social o procedente de empresa de insercion",
}

# ============================================================================
# TDPMUNIC - Codigos de Municipios (INE codes, partial list)
# Key: 2-digit provincia + 3-digit municipio
# ============================================================================
# Not loading full municipality table (8131 entries).
# Will be loaded dynamically from INE data if needed.
MUNICIPALITY_CODES: dict[str, str] = {
    # Alicante province (03)
    "03014": "Alicante/Alacant",
    "03120": "Elche/Elx",
    "03031": "Benidorm",
    "03065": "Elda",
    "03113": "Torrevieja",
    # Madrid province (28)
    "28079": "Madrid",
    "28065": "Getafe",
    "28074": "Leganes",
    "28092": "Mostoles",
    "28127": "Alcorcon",
    # Barcelona province (08)
    "08019": "Barcelona",
    "08101": "L'Hospitalet de Llobregat",
    "08017": "Badalona",
    "08183": "Sabadell",
    "08202": "Terrassa",
    # Valencia province (46)
    "46250": "Valencia",
    "46132": "Torrent",
    "46023": "Gandia",
    # Sevilla province (41)
    "41091": "Sevilla",
    "41037": "Dos Hermanas",
    # Malaga province (29)
    "29067": "Malaga",
    "29054": "Marbella",
}

# ============================================================================
# TDTVINFO - Tipos de Formacion Dual
# ============================================================================
DUAL_TRAINING_TYPES: dict[str, str] = {
    "1": "Formacion Profesional Dual (FP Dual)",
    "2": "Formacion en alternancia con empleo (contrato formacion)",
}

# ============================================================================
# Contracts that require fecha_fin (mandatory end date)
# ============================================================================
CONTRACTS_REQUIRING_END_DATE: set[str] = {
    "402",
    "502",
    "405",
    "505",
    "430",
    "530",
    "412",
    "420",
    "520",
    "421",
    "521",
    "441",
    "541",
    "452",
    "552",
    "970",
}

# ============================================================================
# Contracts where fecha_fin is optional
# ============================================================================
CONTRACTS_OPTIONAL_END_DATE: set[str] = {
    "401",
    "501",
    "404",
    "406",
    "407",
    "506",
    "507",
    "409",
    "509",
    "410",
    "510",
    "540",
    "413",
    "513",
    "980",
    "990",
}

# ============================================================================
# Indefinite contract codes (no end date)
# ============================================================================
INDEFINITE_CONTRACT_CODES: set[str] = {
    "100",
    "130",
    "150",
    "200",
    "230",
    "250",
    "300",
    "330",
    "350",
}

# ============================================================================
# Temporal contract codes
# ============================================================================
TEMPORAL_CONTRACT_CODES: set[str] = {
    "401",
    "402",
    "403",
    "404",
    "405",
    "406",
    "407",
    "409",
    "410",
    "412",
    "413",
    "420",
    "421",
    "430",
    "441",
    "450",
    "452",
    "501",
    "502",
    "503",
    "505",
    "506",
    "507",
    "509",
    "510",
    "513",
    "520",
    "521",
    "530",
    "540",
    "541",
    "550",
    "552",
    "970",
    "980",
    "990",
}

# ============================================================================
# Partial time contract codes (tiempo parcial)
# ============================================================================
PARTIAL_TIME_CONTRACT_CODES: set[str] = {
    "200",
    "230",
    "250",
    "300",
    "330",
    "350",
    "501",
    "502",
    "503",
    "505",
    "506",
    "507",
    "509",
    "510",
    "513",
    "520",
    "521",
    "530",
    "540",
    "541",
    "550",
    "552",
}

# ============================================================================
# Full time contract codes (tiempo completo)
# ============================================================================
FULL_TIME_CONTRACT_CODES: set[str] = {
    "100",
    "130",
    "150",
    "401",
    "402",
    "403",
    "404",
    "405",
    "406",
    "407",
    "409",
    "410",
    "412",
    "413",
    "420",
    "421",
    "430",
    "441",
    "450",
    "452",
    "970",
    "980",
    "990",
}

# ============================================================================
# Contract codes that require IND_DISCAPACIDAD
# ============================================================================
DISABILITY_CONTRACT_CODES: set[str] = {
    "130",
    "230",
    "330",
    "430",
    "530",
}


def get_table(table_name: str) -> dict[str, str]:
    """Get a SEPE code table by name.

    Args:
        table_name: SEPE table code (e.g. 'TNWTPCOM', 'TCHRGCOT')

    Returns:
        Dictionary mapping code -> description

    Raises:
        KeyError: If table name is not found
    """
    tables: dict[str, dict[str, str]] = {
        "TNWTPCOM": CONTRACT_TYPES,
        "TCHRGCOT": COTIZACION_REGIMES,
        "STDIDETC": DOCUMENT_TYPES,
        "TCMCSEXO": GENDER_CODES,
        "TBONVFOR": EDUCATION_LEVELS,
        "TAICLAOC": OCCUPATIONS,
        "TELCOLBO": BONUS_COLLECTIVES,
        "TEJINDIS": DISABILITY_INDICATORS,
        "TEQPTIEM": TIME_PERIODS,
        "TEIINTER": SUBSTITUTION_CAUSES,
        "TETPGMEM": EMPLOYMENT_PROGRAMS,
        "THITIACA": ACADEMIC_QUALIFICATIONS,
        "THYDISLE": LEGAL_PROVISIONS,
        "TBXCPAIS": COUNTRY_CODES,
        "TEYTRELE": RELIEF_WORKER_TYPES,
        "TFGGRCOT": CONTRIBUTION_GROUPS,
        "TXREADEC": ROYAL_DECREE_ADHERENCE,
        "TXORDMIN": MINISTERIAL_ORDERS,
        "TESCETCO": WORKSHOP_SCHOOL_CODES,
        "TEWEINVE": RESEARCH_EMPLOYER_TYPES,
        "TEXTINVE": RESEARCH_WORKER_TYPES,
        "TEUECCLL": LOCAL_CORP_ENTITIES,
        "TEVACTCL": ACTION_CODES,
        "TERFIRCB": BASIC_COPY_SIGNATURE_TYPES,
        "TQOCOLRE": FEE_REDUCTION_COLLECTIVES,
        "TRWCOLDF": TAX_DEDUCTION_COLLECTIVES,
        "TEOCOLDE": INDEFINITE_PROMOTION_COLLECTIVES,
        "THPCOLFO": TRAINING_AGE_COLLECTIVES,
        "TDPMUNIC": MUNICIPALITY_CODES,
        "TCGPROVI": PROVINCE_CODES,
        "TDTVINFO": DUAL_TRAINING_TYPES,
        "BONIFICACIONES": CONTRACT_BONIFICATIONS,
        "BONIFICACION_COLLECTIVES": BONIFICATION_COLLECTIVES,
        "SISTEMA_RED_ERRORS": SISTEMA_RED_ERRORS,
    }
    if table_name not in tables:
        raise KeyError(
            f"Unknown SEPE code table: {table_name}. Available: {', '.join(sorted(tables.keys()))}"
        )
    return tables[table_name]


# ============================================================================
# BONIFICATION RULES - Incentivos a la contratacion (RDL 1/2023 Art. 10)
# ============================================================================
# Maps contract SEPE code prefixes to available bonifications.
# Source: Base de conocimiento laboral (RDL 1/2023 consolidated).

CONTRACT_BONIFICATIONS: dict[str, dict] = {
    # Indefinido bonificado (150, 250, 350)
    "150": {
        "type": "bonificacion_indefinido",
        "amount_eur_month": 128,
        "duration_years": 4,
        "reducible_part_time": True,
        "max_pct_coste_salarial": 60,
        "mantenimiento_min_years": 3,
        "legal_basis": "RDL 1/2023 Art. 10",
    },
    "250": {
        "type": "bonificacion_indefinido_parcial",
        "amount_eur_month": 128,
        "duration_years": 4,
        "reducible_part_time": True,
        "proporcional_jornada": True,
        "legal_basis": "RDL 1/2023 Art. 10",
    },
    "350": {
        "type": "bonificacion_fijo_discontinuo",
        "amount_eur_month": 128,
        "duration_years": 4,
        "reducible_part_time": True,
        "legal_basis": "RDL 1/2023 Art. 10",
    },
    # Conversion formativo -> indefinido
    "_conversion_formativo": {
        "type": "bonificacion_conversion_formativo",
        "amount_eur_month": 128,
        "duration_years": 3,
        "mujer_amount_eur_month": 147,
        "legal_basis": "RDL 1/2023 Art. 10",
        "applies_when": "Transformacion de contrato formativo (421/420) en indefinido",
    },
    # Formativo en alternancia (421) - durante vigencia
    "421": {
        "type": "bonificacion_formativo",
        "amount_eur_month": 91,
        "worker_ss_amount_eur_month": 28,
        "discapacidad_50pct_ss": True,
        "legal_basis": "RDL 1/2023 Art. 10, ET Art. 11.2",
    },
    # Formativo practica profesional (420) - durante vigencia
    "420": {
        "type": "bonificacion_formativo",
        "amount_eur_month": 91,
        "worker_ss_amount_eur_month": 28,
        "legal_basis": "RDL 1/2023 Art. 10, ET Art. 11.1",
    },
}

# Colectivos con bonificacion especifica (mapeo de tipo trabajador -> incentivo)
BONIFICATION_COLLECTIVES: dict[str, dict] = {
    "discapacidad_33+": {
        "description": "Personas con discapacidad >=33%",
        "bonificacion_eur_month": 128,
        "duration_years": 4,
        "subvencion_possible": True,
    },
    "discapacidad_cee": {
        "description": "Personas con discapacidad en Centros Especiales de Empleo",
        "exencion_ss_pct": 100,
        "subvencion_inversion_max_eur": 12000,
    },
    "capacidad_intelectual_limite": {
        "description": "Personas con capacidad intelectual limite (20-33%)",
        "bonificacion_eur_month": 128,
        "duration_years": 4,
        "subvencion_eur": 2000,
    },
    "mujer_violencia_genero": {
        "description": "Mujeres victimas de violencia de genero, violencias sexuales o trata",
        "bonificacion_eur_month": 128,
        "duration_years": 4,
        "no_requires_spe": True,
    },
    "exclusion_social": {
        "description": "Personas trabajadoras en situacion de exclusion social",
        "bonificacion_eur_month": 128,
        "duration_years": 4,
    },
    "empresa_insercion": {
        "description": "Personas en exclusion social en empresas de insercion",
        "bonificacion_eur_month": 70.83,
        "duration_years": 3,
    },
    "joven_garantia_juvenil": {
        "description": "Jovenes <30 con baja cualificacion, beneficiarios Sistema Nacional Garantia Juvenil",
        "bonificacion_eur_month": 275,
        "duration_years": 3,
    },
    "victima_terrorismo": {
        "description": "Personas victimas del terrorismo",
        "bonificacion_eur_month": 128,
        "duration_years": 4,
    },
    "readmitido_ip": {
        "description": "Readmitidos tras incapacidad permanente total o absoluta",
        "bonificacion_eur_month": 128,
        "duration_years": 4,
    },
    "desempleado_larga_duracion": {
        "description": "Personas desempleadas de larga duracion",
        "bonificacion_eur_month": 128,
        "duration_years": 4,
    },
}

# ============================================================================
# SISTEMA RED - Error codes from knowledge base
# ============================================================================
SISTEMA_RED_ERRORS: dict[str, dict] = {
    "5574": {
        "message": "Operación no permitida por TRL del CCC",
        "cause": "Alta en CCC con TRL especial y convenio colectivo no corresponde",
        "solution": "No comunicar convenio colectivo para ese tipo TRL",
    },
    "3718": {
        "message": "No coincide colectivo trabajador con TRL/exc. cotiz.",
        "cause": "Alta en Regimen General Asimilado sin informar 'Colectivo trabajador'",
        "solution": "Introducir valor correcto en casilla Colectivo trabajador",
    },
    "6900": {
        "message": "CNAE09 no válida para tipos cotización AT",
        "cause": "CNAE incompatible con IAE en Agencia Tributaria",
        "solution": "Comprobar IAE en Hacienda. Si correcto, gestion solo en TGSS/CASIA",
    },
    "4796": {
        "message": "El tipo contrato introducido no coincide con el del FIC específico",
        "cause": "En subrogacion, fecha inicio contrato anterior al cambio de tipo",
        "solution": "Informar fecha del contrato vigente, no la del original",
    },
    "4801": {
        "message": "Valor condición desempleado no coincide con valor en el FIC",
        "cause": "Encadenamiento contratos con/sin bonificacion, o subrogacion sin informar condicion",
        "solution": "Marcar FIC específico en segunda alta con fecha real. Revisar último IDC",
    },
    "3168": {
        "message": "Cuenta de cotización en situación de baja",
        "cause": "CCC inactivo >12 meses, falta reinicio",
        "solution": "Reiniciar CCC en Inscripción y Afiliación Real",
    },
    "4849": {
        "message": "Contrato sin peculiaridades de cotización",
        "cause": "Contrato con bonificacion sin informar valores de peculiaridades",
        "solution": "Informar correctamente todos los campos de peculiaridades/bonificacion SS",
    },
    "6361": {
        "message": "No admitida fecha fin contrato temporal",
        "cause": "Baja con situacion distinta a 68/73 con Fecha Fin informada",
        "solution": "Solo informar Fecha Fin para situaciones 68/73 (excedencia cuidado)",
    },
    "4615": {
        "message": "Fecha anterior que fecha de cambio de contrato",
        "cause": "Variacion con fecha anterior al ultimo cambio registrado",
        "solution": "Usar fecha posterior o igual al ultimo cambio de contrato",
    },
    "3016": {
        "message": "No coincide el identificador de personas físicas",
        "cause": "IPF no coincide con base de datos TGSS",
        "solution": "Verificar IPF. Si cambio NIE->DNI, hacer variación IPF primero",
    },
}


def list_tables() -> dict[str, str]:
    """Return all available table names with descriptions."""
    return {
        "TNWTPCOM": "Tipos de Contrato",
        "TCHRGCOT": "Regimenes de Cotizacion",
        "STDIDETC": "Tipos de Documento de Identidad",
        "TCMCSEXO": "Sexo",
        "TBONVFOR": "Niveles Formativos",
        "TAICLAOC": "Ocupaciones (CNO-11)",
        "TELCOLBO": "Colectivos de Bonificacion",
        "TEJINDIS": "Indicador de Discapacidad",
        "TEQPTIEM": "Periodo de Tiempo",
        "TEIINTER": "Causas de Sustitucion",
        "TETPGMEM": "Programas de Empleo",
        "THITIACA": "Titulaciones Academicas",
        "THYDISLE": "Otras Disposiciones Legales",
        "TBXCPAIS": "Paises",
        "TEYTRELE": "Tipos de Trabajador de Relevo",
        "TFGGRCOT": "Grupos de Cotizacion",
        "TXREADEC": "Acogida a Reales Decretos",
        "TXORDMIN": "Ordenes Ministeriales",
        "TESCETCO": "Escuelas Taller / Casa de Oficios",
        "TEWEINVE": "Tipo de Empleador Investigador",
        "TEXTINVE": "Tipo de Trabajador Investigador",
        "TEUECCLL": "Entidades Colaboradoras Corporaciones Locales",
        "TEVACTCL": "Codigos de Actuacion",
        "TERFIRCB": "Tipo de Firma Copia Basica",
        "TQOCOLRE": "Colectivos de Reduccion de Cuotas",
        "TRWCOLDF": "Colectivos de Deduccion Fiscal",
        "TEOCOLDE": "Colectivos Fomento Contratacion Indefinida",
        "THPCOLFO": "Colectivos de Edad en Formacion",
        "TDPMUNIC": "Codigos de Municipios",
        "TCGPROVI": "Codigos de Provincia (INE)",
        "TDTVINFO": "Tipos de Formacion Dual",
        "BONIFICACIONES": "Incentivos contratacion indefinida (RDL 1/2023)",
        "BONIFICACION_COLLECTIVES": "Colectivos con bonificacion especifica",
        "SISTEMA_RED_ERRORS": "Codigos de error habituales Sistema RED",
    }
