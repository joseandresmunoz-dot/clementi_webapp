from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Q
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from appointments.models import Appointment
from files_manager.models import FilePermission, SharedFile
from patients.forms import CategoryForm, ProductForm
from patients.models import AnswerOption, Category, ClinicalTimelineEntry, Lead, Order, PatientProfile, Product, ProductImage, Question, QuizSection, ScoreRange


from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseRedirect


def test_epigenetico(request):
    return render(request, "test_epigenetico.html")


def shop(request):
    categories = Category.objects.filter(is_active=True)
    featured = Product.objects.filter(is_active=True, is_featured=True).select_related("category").prefetch_related("images")

    cat_slug = request.GET.get("categoria")
    if cat_slug:
        products = Product.objects.filter(is_active=True, category__slug=cat_slug).select_related("category").prefetch_related("images")
        selected_category = cat_slug
    else:
        products = Product.objects.filter(is_active=True).select_related("category").prefetch_related("images")
        selected_category = None

    return render(request, "shop.html", {
        "categories": categories,
        "featured": featured,
        "products": products,
        "selected_category": selected_category,
        "cart_count": _cart_count(request),
    })


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related("category").prefetch_related("images"), slug=slug, is_active=True)
    return render(request, "product_detail.html", {
        "product": product,
        "cart_count": _cart_count(request),
    })


def _cart_count(request):
    cart = request.session.get("cart", {})
    return sum(cart.get("items", {}).values())


def add_to_cart(request, product_id):
    if request.method != "POST":
        return redirect("patients:shop")
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart = request.session.get("cart", {"items": {}})
    try:
        qty = int(request.POST.get("quantity", 1))
    except (ValueError, TypeError):
        qty = 1
    current = cart["items"].get(str(product_id), 0)
    cart["items"][str(product_id)] = current + qty
    request.session["cart"] = cart
    messages.success(request, f'"{product.name}" agregado al carrito.')
    return redirect(request.POST.get("next", "patients:shop"))


def remove_from_cart(request, product_id):
    if request.method != "POST":
        return redirect("patients:shop")
    cart = request.session.get("cart", {"items": {}})
    cart["items"].pop(str(product_id), None)
    request.session["cart"] = cart
    messages.success(request, "Producto eliminado del carrito.")
    return redirect("patients:cart")


def cart(request):
    cart_data = request.session.get("cart", {"items": {}})
    items = []
    total = 0
    for pid, qty in cart_data.get("items", {}).items():
        try:
            product = Product.objects.get(id=pid, is_active=True)
        except Product.DoesNotExist:
            continue
        unit_price = float(product.discount_price) if product.is_on_sale and product.discount_price else float(product.price)
        subtotal = unit_price * qty
        items.append({
            "product": product,
            "quantity": qty,
            "unit_price": unit_price,
            "subtotal": subtotal,
        })
        total += subtotal
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item['product'].name} x{item['quantity']} — ${item['subtotal']:.2f}")
    lines.append(f"Total: ${total:.2f}")
    whatsapp_message = "Hola, quiero consultar por los productos de mi carrito:%0A%0A" + "%0A".join(lines)
    return render(request, "cart.html", {
        "items": items,
        "total": total,
        "cart_count": _cart_count(request),
        "whatsapp_message": whatsapp_message,
    })


@user_passes_test(lambda u: u.is_staff)
def shop_admin(request):
    categories = Category.objects.all().order_by("order", "name")
    products = Product.objects.all().select_related("category").order_by("category__order", "order")

    # Stats
    total_orders = Order.objects.count()
    total_revenue = Order.objects.aggregate(t=Sum("total_price"))["t"] or 0
    best_sellers = (
        Order.objects.values("product__name", "product_id")
        .annotate(total_qty=Sum("quantity"), total_rev=Sum("total_price"))
        .order_by("-total_qty")[:10]
    )
    orders_by_status = {
        s: Order.objects.filter(status=s).count()
        for s in ["completed", "pending", "cancelled"]
    }

    cat_form = CategoryForm(prefix="cat")
    prod_form = ProductForm(prefix="prod")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_category":
            cat_form = CategoryForm(request.POST, prefix="cat")
            if cat_form.is_valid():
                cat_form.save()
                messages.success(request, "Categoría creada correctamente.")
                return redirect("patients:shop_admin")
            else:
                messages.error(request, "Corregí los errores del formulario de categoría.")

        elif action == "edit_category":
            cat_id = request.POST.get("cat_id")
            cat = get_object_or_404(Category, id=cat_id)
            cat_form = CategoryForm(request.POST, instance=cat, prefix="cat")
            if cat_form.is_valid():
                cat_form.save()
                messages.success(request, "Categoría actualizada.")
                return redirect("patients:shop_admin")
            else:
                messages.error(request, "Corregí los errores.")

        elif action == "delete_category":
            cat_id = request.POST.get("cat_id")
            cat = get_object_or_404(Category, id=cat_id)
            cat.delete()
            messages.success(request, "Categoría eliminada.")
            return redirect("patients:shop_admin")

        elif action == "add_product":
            prod_form = ProductForm(request.POST, request.FILES, prefix="prod")
            if prod_form.is_valid():
                product = prod_form.save()
                _save_product_images(request, product)
                messages.success(request, "Producto creado correctamente.")
                return redirect("patients:shop_admin")
            else:
                messages.error(request, "Corregí los errores del formulario de producto.")

        elif action == "edit_product":
            prod_id = request.POST.get("prod_id")
            prod = get_object_or_404(Product, id=prod_id)
            prod_form = ProductForm(request.POST, request.FILES, instance=prod, prefix="prod")
            if prod_form.is_valid():
                product = prod_form.save()
                _save_product_images(request, product)
                messages.success(request, "Producto actualizado.")
                return redirect("patients:shop_admin")
            else:
                messages.error(request, "Corregí los errores.")

        elif action == "delete_product":
            prod_id = request.POST.get("prod_id")
            prod = get_object_or_404(Product, id=prod_id)
            prod.delete()
            messages.success(request, "Producto eliminado.")
            return redirect("patients:shop_admin")

    return render(request, "patients/shop_admin.html", {
        "categories": categories,
        "products": products,
        "products_active": products.filter(is_active=True).count(),
        "products_inactive": products.filter(is_active=False).count(),
        "cat_form": cat_form,
        "prod_form": prod_form,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "best_sellers": best_sellers,
        "orders_by_status": orders_by_status,
    })


@require_POST
def capture_lead(request):
    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    phone = request.POST.get("phone", "").strip()
    message = request.POST.get("message", "").strip()
    source = request.POST.get("source", "landing")
    is_subscribed = request.POST.get("is_subscribed", "1") == "1"

    if not name or not email:
        messages.error(request, "Nombre y email son obligatorios.")
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/") + "#contacto")

    Lead.objects.create(
        name=name,
        email=email,
        phone=phone,
        message=message,
        source=source,
        is_subscribed=is_subscribed,
    )
    messages.success(request, "¡Gracias! Te contactaremos pronto.")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/") + "#contacto")


@csrf_exempt
def debug_login(request):
    import traceback
    from django.conf import settings as dj_settings
    from django.contrib.auth import authenticate, login
    from django.http import JsonResponse, HttpResponse
    from allauth import app_settings as allauth_settings

    if request.method == "POST":
        data = {}
        data["method"] = request.method
        data["is_secure"] = request.is_secure()
        data["scheme"] = request.scheme
        data["META_HTTP_REFERER"] = request.META.get("HTTP_REFERER", "")
        data["META_HTTP_ORIGIN"] = request.META.get("HTTP_ORIGIN", "")
        data["META_HTTP_HOST"] = request.META.get("HTTP_HOST", "")
        data["META_CSRF_COOKIE_USED"] = request.META.get("CSRF_COOKIE_USED", False)
        data["META_CSRF_COOKIE_NEEDS_UPDATE"] = request.META.get("CSRF_COOKIE_NEEDS_UPDATE", False)
        data["META_CSRF_COOKIE"] = request.META.get("CSRF_COOKIE", "NOT SET")
        data["COOKIES"] = dict(request.COOKIES)
        data["POST_keys"] = list(request.POST.keys())
        data["login"] = request.POST.get("login", "")
        data["has_pw"] = bool(request.POST.get("password", ""))
        data["ALLOWED_HOSTS"] = dj_settings.ALLOWED_HOSTS
        data["CSRF_TRUSTED_ORIGINS"] = dj_settings.CSRF_TRUSTED_ORIGINS
        data["CSRF_COOKIE_DOMAIN"] = dj_settings.CSRF_COOKIE_DOMAIN
        data["CSRF_COOKIE_NAME"] = dj_settings.CSRF_COOKIE_NAME
        data["SESSION_COOKIE_DOMAIN"] = dj_settings.SESSION_COOKIE_DOMAIN
        data["DJANGO_ALLOWED_HOSTS"] = dj_settings.ALLOWED_HOSTS
        data["SOCIALACCOUNT_ONLY"] = getattr(dj_settings, "SOCIALACCOUNT_ONLY", "NOT SET")
        data["ALLAUTH_SOCIALACCOUNT_ONLY"] = allauth_settings.SOCIALACCOUNT_ONLY

        email = request.POST.get("login", "")
        password = request.POST.get("password", "")
        try:
            user = authenticate(request, email=email, password=password)
            data["authenticate_result"] = str(user) if user else "None"
            if user:
                data["user_active"] = user.is_active
                data["user_staff"] = user.is_staff
                data["user_backend"] = getattr(user, "backend", "NO BACKEND")
                try:
                    login(request, user)
                    data["login_success"] = True
                except Exception as e:
                    data["login_error"] = str(e)
                    data["login_traceback"] = traceback.format_exc()
            else:
                data["auth_failed"] = True
        except Exception as e:
            data["exception"] = str(e)
            data["traceback"] = traceback.format_exc()

        return JsonResponse(data)

    return HttpResponse("Use POST with login=email&password=xxx")


def home(request):
    if request.user.is_authenticated:
        if not _is_patient_approved(request.user) and not request.user.is_staff:
            return redirect("patients:pending_approval")
    return render(request, "landing.html")


@ensure_csrf_cookie
def microbiota_quiz(request):
    sections = QuizSection.objects.filter(is_active=True).prefetch_related(
        "questions__answer_options"
    ).order_by("order")
    score_ranges = list(ScoreRange.objects.all().order_by("min_score").values(
        "name", "min_score", "max_score", "min_score_male", "max_score_male",
        "color", "message_female", "message_male", "order",
    ))
    return render(request, "patients/microbiota_quiz.html", {
        "sections": sections,
        "score_ranges": score_ranges,
    })


@csrf_exempt
@require_POST
def submit_quiz_results(request):
    nombre = request.POST.get("nombre", "").strip()
    email = request.POST.get("email", "").strip()
    telefono = request.POST.get("telefono", "").strip()
    detalles = request.POST.get("detalles", "")
    total = request.POST.get("total", "0")
    mensaje = request.POST.get("mensaje", "")

    if not nombre:
        return JsonResponse({"ok": False, "error": "El nombre es obligatorio."})
    if not email:
        return JsonResponse({"ok": False, "error": "El email es obligatorio."})

    Lead.objects.create(
        name=nombre,
        email=email,
        phone=telefono,
        message=f"Resultados del cuestionario de microbiota:\n"
                f"{detalles}\n"
                f"Total: {total}\n"
                f"Diagnóstico: {mensaje}",
        source="microbiota_quiz",
    )

    asunto = f"Resultados del cuestionario de microbiota — {nombre}"
    cuerpo = (
        f"Nombre: {nombre}\n"
        f"Email: {email}\n"
        f"Teléfono: {telefono}\n\n"
        f"{detalles}\n"
        f"Total: {total}\n"
        f"Diagnóstico: {mensaje}\n"
    )
    send_mail(
        asunto,
        cuerpo,
        settings.DEFAULT_FROM_EMAIL,
        [settings.DEFAULT_FROM_EMAIL],
        fail_silently=True,
    )

    return JsonResponse({"ok": True})


@user_passes_test(lambda u: u.is_staff)
def microbiota_admin(request):
    sections = QuizSection.objects.all().order_by("order")
    questions = Question.objects.all().select_related("section").prefetch_related("answer_options").order_by("section__order", "order")
    score_ranges = ScoreRange.objects.all().order_by("min_score")

    if request.method == "POST":
        action = request.POST.get("action")

        # ── Section CRUD ──
        if action == "add_section":
            name = request.POST.get("name")
            slug = request.POST.get("slug")
            description = request.POST.get("description", "")
            order = request.POST.get("order", 0)
            is_active = request.POST.get("is_active") == "on"
            QuizSection.objects.create(name=name, slug=slug, description=description, order=order, is_active=is_active)
            messages.success(request, "Sección creada correctamente.")
            return redirect("patients:microbiota_admin")

        elif action == "edit_section":
            sec_id = request.POST.get("sec_id")
            sec = get_object_or_404(QuizSection, id=sec_id)
            sec.name = request.POST.get("name")
            sec.slug = request.POST.get("slug")
            sec.description = request.POST.get("description", "")
            sec.order = request.POST.get("order", 0)
            sec.is_active = request.POST.get("is_active") == "on"
            sec.save()
            messages.success(request, "Sección actualizada.")
            return redirect("patients:microbiota_admin")

        elif action == "delete_section":
            sec_id = request.POST.get("sec_id")
            get_object_or_404(QuizSection, id=sec_id).delete()
            messages.success(request, "Sección eliminada.")
            return redirect("patients:microbiota_admin")

        # ── Question CRUD ──
        elif action == "add_question":
            section_id = request.POST.get("section")
            text = request.POST.get("text")
            order = request.POST.get("order", 0)
            is_active = request.POST.get("is_active") == "on"
            q = Question.objects.create(
                section_id=section_id, text=text, order=order, is_active=is_active
            )
            # Save answer options
            opt_texts = request.POST.getlist("opt_text[]")
            opt_points = request.POST.getlist("opt_points[]")
            opt_order = request.POST.getlist("opt_order[]")
            for i in range(len(opt_texts)):
                AnswerOption.objects.create(
                    question=q,
                    text=opt_texts[i],
                    points=opt_points[i],
                    order=opt_order[i] if i < len(opt_order) else i,
                )
            messages.success(request, "Pregunta creada correctamente.")
            return redirect("patients:microbiota_admin")

        elif action == "edit_question":
            q_id = request.POST.get("q_id")
            q = get_object_or_404(Question, id=q_id)
            q.section_id = request.POST.get("section")
            q.text = request.POST.get("text")
            q.order = request.POST.get("order", 0)
            q.is_active = request.POST.get("is_active") == "on"
            q.save()
            # Replace answer options
            q.answer_options.all().delete()
            opt_texts = request.POST.getlist("opt_text[]")
            opt_points = request.POST.getlist("opt_points[]")
            opt_order = request.POST.getlist("opt_order[]")
            for i in range(len(opt_texts)):
                AnswerOption.objects.create(
                    question=q,
                    text=opt_texts[i],
                    points=opt_points[i],
                    order=opt_order[i] if i < len(opt_order) else i,
                )
            messages.success(request, "Pregunta actualizada.")
            return redirect("patients:microbiota_admin")

        elif action == "delete_question":
            q_id = request.POST.get("q_id")
            get_object_or_404(Question, id=q_id).delete()
            messages.success(request, "Pregunta eliminada.")
            return redirect("patients:microbiota_admin")

        # ── Score Range CRUD ──
        elif action == "add_range":
            ScoreRange.objects.create(
                name=request.POST.get("name"),
                min_score=request.POST.get("min_score", 0),
                max_score=request.POST.get("max_score", 0),
                min_score_male=request.POST.get("min_score_male", 0),
                max_score_male=request.POST.get("max_score_male", 0),
                color=request.POST.get("color", "green"),
                message_female=request.POST.get("message_female", ""),
                message_male=request.POST.get("message_male", ""),
                order=request.POST.get("order", 0),
            )
            messages.success(request, "Rango creado correctamente.")
            return redirect("patients:microbiota_admin")

        elif action == "edit_range":
            r_id = request.POST.get("r_id")
            r = get_object_or_404(ScoreRange, id=r_id)
            r.name = request.POST.get("name")
            r.min_score = request.POST.get("min_score", 0)
            r.max_score = request.POST.get("max_score", 0)
            r.min_score_male = request.POST.get("min_score_male", 0)
            r.max_score_male = request.POST.get("max_score_male", 0)
            r.color = request.POST.get("color", "green")
            r.message_female = request.POST.get("message_female", "")
            r.message_male = request.POST.get("message_male", "")
            r.order = request.POST.get("order", 0)
            r.save()
            messages.success(request, "Rango actualizado.")
            return redirect("patients:microbiota_admin")

        elif action == "delete_range":
            r_id = request.POST.get("r_id")
            get_object_or_404(ScoreRange, id=r_id).delete()
            messages.success(request, "Rango eliminado.")
            return redirect("patients:microbiota_admin")

    return render(request, "patients/microbiota_admin.html", {
        "sections": sections,
        "questions": questions,
        "score_ranges": score_ranges,
    })


@login_required
def calendar_view(request):
    if request.user.is_authenticated and not _is_patient_approved(request.user):
        messages.warning(
            request,
            "Tu cuenta aún no fue aprobada por administración."
            " Te avisaremos cuando se habilite.",
        )
        return redirect("patients:pending_approval")
    return render(request, "patients/calendar.html")


def _is_patient_approved(user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    profile = getattr(user, "patient_profile", None)
    return bool(profile and profile.is_approved)


def _calculate_age(date_of_birth):
    if not date_of_birth:
        return None
    today = date.today()
    years = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years


@login_required
def dashboard(request):
    if not _is_patient_approved(request.user):
        messages.warning(
            request,
            "Tu cuenta aún no fue aprobada por administración."
            " Te avisaremos cuando se habilite.",
        )
        return redirect("patients:pending_approval")

    today = date.today()
    user = request.user

    upcoming_appointments = (
        Appointment.objects.filter(
            patient=user,
            status=Appointment.Status.BOOKED,
            date__gte=today,
        )
        .order_by("date", "start_time")
    )

    past_count = Appointment.objects.filter(
        patient=user,
        status=Appointment.Status.COMPLETED,
    ).count()

    # Archivos: públicos + registrados + privados asignados al paciente
    private_ids = FilePermission.objects.filter(patient=user).values_list(
        "shared_file_id", flat=True
    )
    files = SharedFile.objects.filter(
        Q(visibility=SharedFile.Visibility.PUBLIC)
        | Q(visibility=SharedFile.Visibility.REGISTERED)
        | Q(visibility=SharedFile.Visibility.PRIVATE, id__in=private_ids)
    ).order_by("-created_at")

    timeline_entries = ClinicalTimelineEntry.objects.filter(patient=user).select_related("created_by", "appointment")

    context = {
        "upcoming_appointments": upcoming_appointments,
        "upcoming_count": upcoming_appointments.count(),
        "past_count": past_count,
        "files_count": files.count(),
        "files": files,
        "timeline_entries": timeline_entries,
    }
    return render(request, "patients/dashboard.html", context)


@login_required
def pending_approval(request):
    if request.user.is_staff:
        return redirect("patients:admin_panel")
    if _is_patient_approved(request.user):
        return redirect("patients:dashboard")
    return render(request, "patients/pending_approval.html")


@user_passes_test(lambda u: u.is_staff)
def patients_admin_list(request):
    patients_qs = PatientProfile.objects.select_related("user").filter(user__is_staff=False)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_patient":
            email = (request.POST.get("email") or "").strip().lower()
            first_name = (request.POST.get("first_name") or "").strip()
            last_name = (request.POST.get("last_name") or "").strip()
            password = request.POST.get("password")

            errors = []
            if not email:
                errors.append("El correo electrónico es obligatorio.")
            if User.objects.filter(email=email).exists():
                errors.append("Ya existe un usuario con ese correo electrónico.")
            if not password or len(password) < 6:
                errors.append("La contraseña debe tener al menos 6 caracteres.")

            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    password=password,
                )
                profile, created = PatientProfile.objects.get_or_create(user=user)
                profile.is_approved = True
                profile.approved_at = timezone.now()
                profile.approved_by = request.user
                profile.save(update_fields=["is_approved", "approved_at", "approved_by", "updated_at"])
                messages.success(
                    request,
                    f"Paciente {first_name or last_name or email} creado y aprobado correctamente.",
                )

            return redirect("patients:patients_admin_list")

        profile_id = request.POST.get("profile_id")
        profile = get_object_or_404(patients_qs, id=profile_id)

        if action == "approve":
            profile.is_approved = True
            profile.approved_at = timezone.now()
            profile.approved_by = request.user
            profile.save(update_fields=["is_approved", "approved_at", "approved_by", "updated_at"])
            messages.success(request, "Paciente aprobado correctamente.")
        elif action == "revoke":
            profile.is_approved = False
            profile.approved_at = None
            profile.approved_by = None
            profile.save(update_fields=["is_approved", "approved_at", "approved_by", "updated_at"])
            messages.warning(request, "Aprobación del paciente revocada.")
        elif action == "reject":
            user_email = profile.user.email
            profile.user.delete()
            messages.warning(request, f"Paciente rechazado y eliminado: {user_email}")

        return redirect("patients:patients_admin_list")

    context = {
        "pending_profiles": patients_qs.filter(is_approved=False).order_by("created_at"),
        "approved_profiles": patients_qs.filter(is_approved=True).order_by("user__last_name", "user__first_name"),
    }
    return render(request, "patients/patients_admin_list.html", context)


@user_passes_test(lambda u: u.is_staff)
def patient_admin_detail(request, profile_id):
    profile = get_object_or_404(
        PatientProfile.objects.select_related("user", "approved_by"),
        id=profile_id,
        user__is_staff=False,
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_profile_note":
            profile.phone = (request.POST.get("phone") or "").strip()
            profile.locality = (request.POST.get("locality") or "").strip()
            dob_raw = (request.POST.get("date_of_birth") or "").strip()
            profile.date_of_birth = parse_date(dob_raw) if dob_raw else None
            profile.notes = request.POST.get("profile_note", "")
            profile.save(update_fields=["phone", "locality", "date_of_birth", "notes", "updated_at"])
            messages.success(request, "Historia clínica general actualizada.")
            return redirect("patients:patient_admin_detail", profile_id=profile.id)

        subject = (request.POST.get("subject") or "").strip()
        details = (request.POST.get("details") or "").strip()
        appointment_id = request.POST.get("appointment_id") or ""

        if not subject or not details:
            messages.error(request, "Completá asunto y detalle para guardar la entrada clínica.")
        else:
            appointment = None
            if appointment_id:
                appointment = Appointment.objects.filter(
                    id=appointment_id,
                    patient=profile.user,
                ).first()
            ClinicalTimelineEntry.objects.create(
                patient=profile.user,
                subject=subject,
                details=details,
                appointment=appointment,
                created_by=request.user,
            )
            messages.success(request, "Entrada clínica guardada.")
            return redirect("patients:patient_admin_detail", profile_id=profile.id)

    appointments = Appointment.objects.filter(patient=profile.user).order_by("-date", "-start_time")
    timeline_entries = ClinicalTimelineEntry.objects.filter(patient=profile.user).select_related("created_by", "appointment")

    context = {
        "profile": profile,
        "appointments": appointments,
        "timeline_entries": timeline_entries,
        "patient_age": _calculate_age(profile.date_of_birth),
    }
    return render(request, "patients/patient_admin_detail.html", context)


@user_passes_test(lambda u: u.is_staff)
def admin_panel(request):
    today = date.today()
    week_end = today + timedelta(days=7)

    total_patients = PatientProfile.objects.count()

    today_appointments = Appointment.objects.filter(
        date=today,
        status__in=[Appointment.Status.BOOKED, Appointment.Status.AVAILABLE],
    ).count()

    week_booked = Appointment.objects.filter(
        date__gte=today,
        date__lte=week_end,
        status=Appointment.Status.BOOKED,
    ).count()

    upcoming_appointments = (
        Appointment.objects.filter(date__gte=today)
        .exclude(status=Appointment.Status.CANCELLED)
        .select_related("patient")
        .order_by("date", "start_time")[:15]
    )

    context = {
        "total_patients": total_patients,
        "today_appointments": today_appointments,
        "week_booked": week_booked,
        "upcoming_appointments": upcoming_appointments,
    }
    return render(request, "patients/admin_panel.html", context)


def _save_product_images(request, product):
    images = request.FILES.getlist("prod-images")
    cover_index = int(request.POST.get("prod-cover-index", 0))
    for i, f in enumerate(images):
        ProductImage.objects.create(
            product=product,
            image=f,
            is_cover=(i == cover_index),
            order=i,
        )
