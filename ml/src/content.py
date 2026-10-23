"""Textos para la interfaz: qué hacer según la enfermedad y el nivel de riesgo.

Basado en medidas de prevención difundidas por el MINSA. No reemplaza la consulta médica.
"""

DISEASE_INFO = {
    "dengue": {
        "nombre": "Dengue",
        "icono": "mosquito",
        "causa": "Lo transmite el zancudo Aedes aegypti, que se cría en agua acumulada tras las lluvias.",
        "sintomas": "Fiebre alta, dolor de cabeza, detrás de los ojos, en músculos y articulaciones.",
        "senal_alarma": "Dolor abdominal intenso, vómitos persistentes, sangrado de encías o nariz, somnolencia.",
        "relacionadas": "Zika y chikungunya se transmiten por el mismo zancudo; la malaria, por otro mosquito en zonas con charcos.",
    },
    "leptospirosis": {
        "nombre": "Leptospirosis",
        "icono": "water",
        "causa": "Se contagia al caminar por aguas estancadas con orina de roedores u otros animales.",
        "sintomas": "Fiebre, dolor muscular (sobre todo pantorrillas), ojos rojos, dolor de cabeza.",
        "senal_alarma": "Piel u ojos amarillos, poca orina, dificultad para respirar.",
        "relacionadas": "También aumentan hongos e infecciones de la piel por contacto con lodo y agua contaminada.",
    },
    "eda": {
        "nombre": "Diarreas (EDA)",
        "icono": "droplet",
        "causa": "Agua no potable o alimentos mal lavados; las inundaciones dañan el desagüe.",
        "sintomas": "Diarrea, vómitos, dolor de estómago.",
        "senal_alarma": "Sangre en las heces, mucha sed, boca seca, no orina, niño decaído.",
        "relacionadas": "Cólera, fiebre tifoidea y hepatitis A se transmiten por la misma vía (agua y alimentos contaminados).",
    },
    "golpe_calor": {
        "nombre": "Golpe de calor",
        "icono": "sun",
        "causa": "Temperaturas extremas que El Niño eleva sobre lo normal.",
        "sintomas": "Piel caliente y seca, mareo, dolor de cabeza, náuseas.",
        "senal_alarma": "Confusión, desmayo, fiebre muy alta sin sudor.",
        "relacionadas": "Deshidratación, sobre todo en niños pequeños y adultos mayores.",
    },
    "ira": {
        "nombre": "Infecciones respiratorias (IRA)",
        "icono": "lungs",
        "causa": "Cambios bruscos de temperatura y humedad que favorecen virus respiratorios.",
        "sintomas": "Tos, dolor de garganta, fiebre, congestión.",
        "senal_alarma": "Respiración rápida o con silbido, hundimiento de costillas en niños, labios morados.",
        "relacionadas": "Bronquitis, neumonía y crisis de asma; conjuntivitis por polvo o falta de higiene.",
    },
}

CITIZEN_ACTIONS = {
    "dengue": [
        "Elimina objetos que acumulen agua: llantas, tapas, baldes y botellas.",
        "Tapa bien tanques y baldes donde guardas agua y lávalos cada semana con escobilla.",
        "Usa repelente y mosquiteros; si tienes fiebre, acude al centro de salud y no te automediques.",
    ],
    "leptospirosis": [
        "No camines descalzo ni con heridas por zonas inundadas o con lodo.",
        "Usa botas y guantes si limpias después de una inundación.",
        "Guarda los alimentos tapados y lejos de roedores.",
    ],
    "eda": [
        "Bebe solo agua hervida, tratada o embotellada.",
        "Lávate las manos con agua y jabón antes de comer y después de ir al baño.",
        "Come alimentos bien cocidos y lava frutas y verduras con agua segura.",
    ],
    "golpe_calor": [
        "Toma agua seguido aunque no tengas sed.",
        "Evita el sol entre las 10 a. m. y las 4 p. m.; usa gorro y ropa ligera.",
        "Cuida a niños pequeños y adultos mayores: nunca los dejes en un auto cerrado.",
    ],
    "ira": [
        "Abrígate ante los cambios bruscos de temperatura, sobre todo de noche.",
        "Lávate las manos y cubre tu boca al toser.",
        "Ventila tu casa y mantén al día las vacunas de niños y adultos mayores.",
    ],
}

AUTHORITY_ACTIONS = {
    "dengue": {
        "alto": [
            "Programar fumigación espacial y control larvario casa por casa en las próximas 2 semanas.",
            "Abastecer pruebas rápidas de dengue (NS1/IgM): ~{tests} unidades estimadas.",
            "Preparar sales de rehidratación y camas de observación: ~{beds} camas estimadas.",
            "Activar comunicación de riesgo y búsqueda activa de febriles.",
        ],
        "medio": [
            "Intensificar vigilancia entomológica (índice aédico) y recojo de inservibles.",
            "Verificar stock de pruebas rápidas: ~{tests} unidades como referencia.",
            "Capacitar al personal en el manejo de casos con signos de alarma.",
        ],
        "bajo": [
            "Mantener vigilancia rutinaria y campañas de eliminación de criaderos.",
        ],
    },
    "leptospirosis": {
        "alto": ["Alertar a la población sobre aguas estancadas y coordinar desratización.",
                 "Revisar stock de tratamiento según la guía técnica del MINSA."],
        "medio": ["Difundir medidas de protección en zonas inundables."],
        "bajo": ["Vigilancia rutinaria."],
    },
    "eda": {
        "alto": ["Distribuir cloro y sales de rehidratación oral; vigilar calidad del agua.",
                 "Coordinar con la EPS de saneamiento la revisión de redes dañadas."],
        "medio": ["Reforzar mensajes de agua segura y lavado de manos."],
        "bajo": ["Vigilancia rutinaria."],
    },
    "golpe_calor": {
        "alto": ["Emitir alerta por calor extremo y habilitar puntos de hidratación.",
                 "Priorizar visitas a adultos mayores y niños pequeños."],
        "medio": ["Difundir recomendaciones de hidratación y horarios de exposición al sol."],
        "bajo": ["Vigilancia rutinaria."],
    },
    "ira": {
        "alto": ["Reforzar la atención de IRA en niños y adultos mayores y revisar stock de oxígeno.",
                 "Campaña de vacunación (influenza, neumococo) en grupos de riesgo."],
        "medio": ["Difundir medidas de abrigo y lavado de manos."],
        "bajo": ["Vigilancia rutinaria."],
    },
}

LEVELS = {
    "alto": {"label": "Riesgo alto", "color": "rojo"},
    "medio": {"label": "Riesgo medio", "color": "ambar"},
    "bajo": {"label": "Riesgo bajo", "color": "verde"},
}
LEVEL_THRESHOLDS = {"alto": 0.6, "medio": 0.3}  # probabilidad


def level_of(prob):
    if prob >= LEVEL_THRESHOLDS["alto"]:
        return "alto"
    if prob >= LEVEL_THRESHOLDS["medio"]:
        return "medio"
    return "bajo"


# ---------------------------------------------------------------------------------------------
# Lluvias extremas (inundación y huaico). Recomendaciones generales de gestión de riesgo; deben
# alinearse con los protocolos de INDECI y la DIRESA de cada región.
# ---------------------------------------------------------------------------------------------
FLOOD_INFO = {
    "nombre": "Lluvias extremas (inundación y huaico)",
    "icono": "rain",
    "causa": "Lluvias muy por encima de lo normal para tu distrito pueden desbordar ríos y quebradas, inundar calles y activar huaicos.",
    "despues": "Después de una inundación aumentan la leptospirosis, las diarreas y el dengue (agua estancada y desagües dañados).",
}

FLOOD_ACTIONS_CITIZEN = {
    "alto": [
        "Prepara una mochila de emergencia: agua, linterna, documentos, botiquín y medicinas de uso diario.",
        "Ubica tu zona segura y tu ruta de evacuación; si las autoridades indican evacuar, hazlo de inmediato.",
        "No cruces ríos, quebradas ni calles inundadas, ni a pie ni en vehículo.",
        "Después de la inundación: no camines descalzo por el agua, hierve el agua para beber y elimina charcos donde se cría el zancudo.",
    ],
    "medio": [
        "Revisa tu techo, canaletas y desagües, y mantenlos limpios.",
        "Ten a mano una linterna, agua y tus documentos en una bolsa cerrada.",
        "Evita pasar por quebradas y calles que se empozan; infórmate por las alertas de tu municipalidad.",
    ],
    "bajo": [
        "No hay alerta de lluvias extremas ahora. Aun así, mantén limpios los desagües y conoce tu zona segura.",
    ],
}

FLOOD_ACTIONS_AUTHORITY = {
    "alto": [
        "Activar el Centro de Operaciones de Emergencia y coordinar con Defensa Civil las zonas y rutas de evacuación.",
        "Trasladar medicamentos, pruebas rápidas, cloro y vacunas a establecimientos en zona alta; asegurar la cadena de frío y la energía.",
        "Verificar el acceso a establecimientos que podrían quedar aislados y definir brigadas móviles.",
        "Programar para 1–2 semanas después del evento: control larvario, cloración del agua y vigilancia de leptospirosis y diarreas.",
    ],
    "medio": [
        "Reforzar la limpieza de drenajes y canales con la municipalidad y difundir las alertas a la población.",
        "Verificar el stock de cloro, sales de rehidratación y pruebas rápidas.",
        "Mantener comunicación con Defensa Civil y vigilar el pronóstico a diario.",
    ],
    "bajo": ["Mantener la vigilancia del pronóstico."],
}
