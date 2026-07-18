from django.db import migrations


def seed_microbiota_questions(apps, schema_editor):
    QuizSection = apps.get_model("patients", "QuizSection")
    Question = apps.get_model("patients", "Question")
    AnswerOption = apps.get_model("patients", "AnswerOption")
    ScoreRange = apps.get_model("patients", "ScoreRange")

    # ── Sections ──
    sec_a, _ = QuizSection.objects.get_or_create(
        slug="historia", defaults={
            "name": "Sección A: Historia",
            "description": "Respondé Sí o No a cada pregunta",
            "order": 0,
        }
    )
    sec_b, _ = QuizSection.objects.get_or_create(
        slug="sintomas", defaults={
            "name": "Sección B: Síntomas",
            "description": "Indicá la intensidad de cada síntoma que padezcas o hayas padecido",
            "order": 1,
        }
    )
    sec_c, _ = QuizSection.objects.get_or_create(
        slug="otros-sintomas", defaults={
            "name": "Sección C: Otros Síntomas",
            "description": "Indicá la intensidad de cada síntoma que padezcas o hayas padecido",
            "order": 2,
        }
    )

    # ── Helper ──
    def add_q(section, text, options):
        q = Question.objects.create(section=section, text=text, order=len(options))
        for i, (opt_text, points) in enumerate(options):
            AnswerOption.objects.create(question=q, text=opt_text, points=points, order=i)
        return q

    # ── Section A (Historia): 15 questions ──
    add_q(sec_a, "¿Has tomado algún antibiótico por más de 1 mes para acné o alguna otra causa?", [
        ("No", 0), ("Sí", 25),
    ])
    add_q(sec_a, "¿Has tomado antibióticos de amplio espectro para alguna infección (respiratoria, urinaria, etc.) por más de dos meses o en intervalos pequeños en más de 4 ocasiones en un año?", [
        ("No", 0), ("Sí", 20),
    ])
    add_q(sec_a, "¿Has tomado antibióticos de amplio espectro aunque sea en una sola dosis?", [
        ("No", 0), ("Sí", 25),
    ])
    add_q(sec_a, "¿Alguna vez has tenido síntomas persistentes de prostatitis, vaginitis, o algún otro problema de órganos reproductores?", [
        ("No", 0), ("Sí", 25),
    ])
    add_q(sec_a, "¿Alguna vez has tenido problemas de concentración, memoria o algunas veces te sentís \"en las nubes\"?", [
        ("No", 0), ("Sí", 10),
    ])
    add_q(sec_a, "¿Te sentís enfermo/a por todo a pesar de haber ido a muchos médicos y no encuentran qué tenés?", [
        ("No", 0), ("Sí", 5),
    ])
    add_q(sec_a, "¿Has estado embarazada?", [
        ("No", 0), ("Una vez", 3), ("Dos o más veces", 5),
    ])
    add_q(sec_a, "¿Has tomado pastillas anticonceptivas?", [
        ("No", 0), ("6 meses a 2 años", 8), ("Más de 2 años", 15),
    ])
    add_q(sec_a, "¿Has tomado cortisona o esteroides (orales, inyectados o inhalados)?", [
        ("No", 0), ("2 semanas o menos", 6), ("Más de 2 semanas", 15),
    ])
    add_q(sec_a, "¿La exposición a perfumes, insecticidas, olores de fábrica y otros químicos te provocan síntomas?", [
        ("No", 0), ("Leves", 5), ("Moderados a severos", 20),
    ])
    add_q(sec_a, "¿El olor del tabaco te molesta?", [
        ("No", 0), ("Sí", 10),
    ])
    add_q(sec_a, "¿Tus síntomas tienden a empeorar en lugares húmedos, bochornosos o enmohecidos?", [
        ("No", 0), ("Sí", 20),
    ])
    add_q(sec_a, "¿Has tenido pie de atleta u otra infección de hongos en piel o uñas?", [
        ("No", 0), ("Leve", 10), ("Moderado a severo", 20),
    ])
    add_q(sec_a, "¿Se te antoja mucho el azúcar?", [
        ("No", 0), ("Sí", 10),
    ])
    add_q(sec_a, "¿Tenés ansias de pan?", [
        ("No", 0), ("Sí", 10),
    ])

    # ── Section B (Síntomas): 23 questions, points: 0/3/6/9 ──
    sec_b_qs = [
        "Fatiga o Letargo",
        "Sensación de estar drenado/a",
        "Depresión o Maníaco-depresivo",
        "Adormecimiento, quemazón u hormigueo",
        "Dolores de cabeza",
        "Dolores musculares",
        "Debilidad muscular o parálisis",
        "Dolor o hinchazón en articulaciones",
        "Dolor abdominal",
        "Estreñimiento y/o Diarrea",
        "Hinchazón abdominal, gases, eruptos",
        "Ardor, comezón o flujo vaginal",
        "Prostatitis",
        "Impotencia",
        "Baja en libido",
        "Endometriosis o infertilidad",
        "Cólicos menstruales o irregularidades menstruales",
        "Síndrome premenstrual",
        "Ataques de ansiedad o de llorar",
        "Manos y pies fríos, temperatura baja",
        "Hipotiroidismo",
        "Irritable cuando tenés hambre",
        "Cistitis (infección de vejiga)",
    ]
    for i, q_text in enumerate(sec_b_qs):
        add_q(sec_b, q_text, [
            ("No", 0),
            ("Ocasional o leve", 3),
            ("Frecuente o moderado", 6),
            ("Severo o incapacitante", 9),
        ])

    # ── Section C (Otros Síntomas): 33 questions, points: 0/1/2/3 ──
    sec_c_qs = [
        "Mareado/a",
        "Irritable",
        "Incoordinación",
        "Cambiás mucho de humor",
        "Insomnio",
        "Pérdida de balance",
        "Presión arriba de los oídos o sentir que la cabeza está hinchada",
        "Problemas de Sinusitis",
        "Tendencia a que te salgan moretones fácil",
        "Eczema o irritación de ojos",
        "Psoriasis",
        "Urticaria (crónica)",
        "Indigestión o reflujo",
        "Sensibilidad a la leche, trigo, maíz u otras comidas",
        "Moco en las heces",
        "Comezón anal",
        "Boca y garganta seca",
        "Lengua blanca o irritación en la boca",
        "Mal aliento",
        "Olores en pies, pelo y cuerpo que no se quitan aún después de bañarse",
        "Congestión nasal y goteo retronasal",
        "Comezón en nariz",
        "Dolor de garganta",
        "Laringitis",
        "Tos o bronquitis recurrente",
        "Dolor o presión en el pecho",
        "Jadeo o falta de aliento",
        "Urgencia para orinar",
        "Ardor al orinar",
        "Visión errática o puntos en la visión",
        "Ardor en ojos o constante lagrimeo",
        "Infecciones recurrentes en los oídos",
        "Dolores en oídos o sordera",
    ]
    for i, q_text in enumerate(sec_c_qs):
        add_q(sec_c, q_text, [
            ("No", 0),
            ("Ocasional o leve", 1),
            ("Frecuente o moderado", 2),
            ("Severo o incapacitante", 3),
        ])

    # ── Score Ranges ──
    ScoreRange.objects.get_or_create(
        name="Poco probable", defaults={
            "min_score": 0, "max_score": 59,
            "min_score_male": 0, "max_score_male": 39,
            "color": "green",
            "message_female": "Es poco probable que la cándida sea la causante de sus problemas de salud.",
            "message_male": "Es poco probable que la cándida sea la causante de sus problemas de salud.",
            "order": 0,
        }
    )
    ScoreRange.objects.get_or_create(
        name="Algunas posibilidades", defaults={
            "min_score": 60, "max_score": 119,
            "min_score_male": 40, "max_score_male": 89,
            "color": "yellow",
            "message_female": "Hay algunas posibilidades de que la cándida sea la causante de sus problemas de salud.",
            "message_male": "Hay algunas posibilidades de que la cándida sea la causante de sus problemas de salud.",
            "order": 1,
        }
    )
    ScoreRange.objects.get_or_create(
        name="Probable", defaults={
            "min_score": 120, "max_score": 179,
            "min_score_male": 90, "max_score_male": 139,
            "color": "red",
            "message_female": "Es probable que la cándida sea la causante de sus problemas de salud.",
            "message_male": "Es probable que la cándida sea la causante de sus problemas de salud.",
            "order": 2,
        }
    )
    ScoreRange.objects.get_or_create(
        name="Muy probable", defaults={
            "min_score": 180, "max_score": 9999,
            "min_score_male": 140, "max_score_male": 9999,
            "color": "red",
            "message_female": "Es muy probable que la cándida sea la causante de sus problemas de salud.",
            "message_male": "Es muy probable que la cándida sea la causante de sus problemas de salud.",
            "order": 3,
        }
    )


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0012_scorerange_max_score_male_scorerange_min_score_male_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_microbiota_questions),
    ]
