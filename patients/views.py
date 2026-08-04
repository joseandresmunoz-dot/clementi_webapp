import secrets
import uuid
from datetime import date, timedelta

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Q
from django.db.models import Count, Sum
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import urlencode
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST
import logging

logger = logging.getLogger(__name__)

from appointments.models import Appointment
from files_manager.models import FilePermission, SharedFile
from patients import services
from patients.forms import CategoryForm, LeadReplyForm, ProductForm
from patients.models import (
    AnswerOption,
    Category,
    ClinicalTimelineEntry,
    GoogleCalendarCredentials,
    Lead,
    LeadReply,
    MercadoPagoCredentials,
    Order,
    PatientProfile,
    Product,
    ProductImage,
    Question,
    QuizSection,
    ScoreRange,
)


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


def checkout_mp(request):
    """
    Crea una preferencia de Checkout Pro con el carrito actual y redirige al
    link de pago (`init_point`) de Mercado Pago.
    """
    cart_data = request.session.get("cart", {"items": {}})
    raw_items = cart_data.get("items", {})
    if not raw_items:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect("patients:cart")

    items = []
    for pid, qty in raw_items.items():
        try:
            product = Product.objects.get(id=pid, is_active=True)
        except Product.DoesNotExist:
            continue
        unit_price = (
            float(product.discount_price)
            if product.is_on_sale and product.discount_price
            else float(product.price)
        )
        items.append({
            "title": product.name,
            "quantity": int(qty),
            "unit_price": round(unit_price, 2),
        })

    if not items:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect("patients:cart")

    # La preferencia se crea con la cuenta del vendedor conectada a MP.
    seller = services.get_connected_seller()
    if not seller:
        messages.error(
            request,
            "Aún no hay una cuenta de Mercado Pago conectada. "
            "Conectala desde el panel de administración para empezar a cobrar.",
        )
        return redirect("patients:cart")

    reference = f"cart-{request.session.session_key or uuid.uuid4().hex}"

    try:
        preference = services.create_checkout_preference(
            seller,
            items,
            external_reference=reference,
        )
    except services.MercadoPagoError as exc:
        messages.error(request, f"No se pudo iniciar el pago: {exc}")
        return redirect("patients:cart")

    init_point = preference.get("init_point")
    if not init_point:
        messages.error(request, "Mercado Pago no devolvió el link de pago.")
        return redirect("patients:cart")

    return redirect(init_point)


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
        "mp_is_connected": hasattr(request.user, "mp_credentials")
        and request.user.mp_credentials.is_connected,
    })


def _notify_staff_new_lead(lead):
    """Envía notificación push a todos los staff cuando llega una consulta nueva."""
    try:
        from webpush import send_user_notification
    except ImportError:
        logger.warning("django-webpush no instalado, no se envía push.")
        return

    payload = {
        "head": "Nueva consulta desde la web",
        "body": (
            f"{lead.name}: {lead.message[:100]}..."
            if lead.message
            else f"{lead.name} te contactó"
        ),
        "icon": "/static/img/logo.png",
        "badge": "/static/img/logo.png",
        "url": "/consultas/",
        "actions": [{"action": "open", "title": "Ver consulta"}],
    }

    staff_users = User.objects.filter(is_staff=True, is_active=True)
    for user in staff_users:
        try:
            send_user_notification(user, payload, ttl=3600)
        except Exception:
            logger.debug("No se pudo enviar push a %s", user.username)


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

    _notify_staff_new_lead(
        Lead.objects.filter(email=email).order_by("-created_at").first()
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

    _notify_staff_new_lead(
        Lead.objects.filter(email=email).order_by("-created_at").first()
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
        "leads": Lead.objects.order_by("-created_at")[:5],
        "mp_is_connected": hasattr(request.user, "mp_credentials")
        and request.user.mp_credentials.is_connected,
        "google_calendar_is_connected": hasattr(
            request.user, "google_calendar_credentials"
        )
        and request.user.google_calendar_credentials.is_connected,
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


def _mp_redirect_uri(request):
    """URL de redirección registrada en MP, o la del callback actual si no se configuró."""
    return settings.MP_REDIRECT_URI or request.build_absolute_uri(
        reverse("patients:mp_callback")
    )


@user_passes_test(lambda u: u.is_staff)
def mp_connect(request):
    """
    Inicia el flujo OAuth 2.0: redirige al vendedor a la pantalla de
    autorización de Mercado Pago (response_type=code, platform_id=mp).
    """
    if not settings.MP_CLIENT_ID or not settings.MP_CLIENT_SECRET:
        messages.error(
            request,
            "Falta configurar MP_CLIENT_ID y MP_CLIENT_SECRET en el .env "
            "para poder conectar la cuenta de Mercado Pago.",
        )
        return redirect("patients:shop_admin")

    state = secrets.token_urlsafe(32)
    request.session["mp_oauth_state"] = state

    params = {
        "client_id": settings.MP_CLIENT_ID,
        "response_type": "code",
        "platform_id": "mp",
        "redirect_uri": _mp_redirect_uri(request),
        "state": state,
    }
    return redirect(f"{settings.MP_AUTH_URL}?{urlencode(params)}")


@user_passes_test(lambda u: u.is_staff)
def mp_callback(request):
    """
    Procesa la respuesta de MP tras el consentimiento: canjea el ``code`` por
    las credenciales (grant_type=authorization_code) y las guarda vinculadas
    al vendedor autenticado.
    """
    code = request.GET.get("code")
    error = request.GET.get("error")
    state = request.GET.get("state")

    if error:
        messages.error(request, f"La conexión fue rechazada por Mercado Pago: {error}")
        return redirect("patients:shop_admin")

    if not code:
        messages.error(request, "Mercado Pago no devolvió un código de autorización.")
        return redirect("patients:shop_admin")

    if state != request.session.pop("mp_oauth_state", None):
        messages.error(request, "El estado de la autorización no coincide.")
        return redirect("patients:shop_admin")

    data = {
        "grant_type": "authorization_code",
        "client_id": settings.MP_CLIENT_ID,
        "client_secret": settings.MP_CLIENT_SECRET,
        "code": code,
        "redirect_uri": _mp_redirect_uri(request),
    }

    try:
        response = requests.post(settings.MP_TOKEN_URL, data=data, timeout=30)
    except requests.RequestException as exc:
        messages.error(request, f"No se pudo contactar a Mercado Pago: {exc}")
        return redirect("patients:shop_admin")

    if response.status_code != 200:
        messages.error(
            request,
            "Mercado Pago rechazó la conexión "
            f"(HTTP {response.status_code}). Verificá CLIENT_ID, "
            "CLIENT_SECRET y REDIRECT_URI.",
        )
        return redirect("patients:shop_admin")

    credentials, _ = MercadoPagoCredentials.objects.get_or_create(user=request.user)
    credentials.update_from_token(response.json())

    messages.success(
        request, "Tu cuenta de Mercado Pago se conectó correctamente."
    )
    return redirect("patients:shop_admin")


def _google_oauth_app():
    """Devuelve el dict ``APP`` de allauth para Google (client_id/secret)."""
    return settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("APP", {})


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


@user_passes_test(lambda u: u.is_staff)
def connect_google_calendar(request):
    """
    Inicia el flujo OAuth2 de Google Calendar para la Dra. (scope de calendar
    solo acá; el login normal de pacientes no pide scopes sensibles).
    """
    app = _google_oauth_app()
    client_id = app.get("client_id", "")
    client_secret = app.get("secret", "")
    if not client_id or not client_secret:
        messages.error(
            request,
            "Falta configurar GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET "
            "en el .env para conectar Google Calendar.",
        )
        return redirect("patients:admin_panel")

    state = secrets.token_urlsafe(32)
    request.session["google_calendar_state"] = state

    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": f"{GOOGLE_CALENDAR_SCOPE} openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "redirect_uri": request.build_absolute_uri(
            reverse("patients:google_calendar_callback")
        ),
        "state": state,
    }
    return redirect(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@user_passes_test(lambda u: u.is_staff)
def google_calendar_callback(request):
    """
    Procesa la respuesta de Google tras el consentimiento: canjea el ``code``
    por las credenciales y las guarda en ``GoogleCalendarCredentials``.
    """
    state = request.GET.get("state")
    if not state or state != request.session.pop("google_calendar_state", None):
        messages.error(request, "La solicitud no es válida (state incorrecto).")
        return redirect("patients:admin_panel")

    error = request.GET.get("error")
    if error:
        messages.error(request, f"No se pudo conectar Google Calendar: {error}")
        return redirect("patients:admin_panel")

    code = request.GET.get("code")
    if not code:
        messages.error(request, "Google no devolvió un código de autorización.")
        return redirect("patients:admin_panel")

    app = _google_oauth_app()
    client_id = app.get("client_id", "")
    client_secret = app.get("secret", "")
    redirect_uri = request.build_absolute_uri(
        reverse("patients:google_calendar_callback")
    )

    try:
        token_resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        token_resp.raise_for_status()
        payload = token_resp.json()
    except requests.RequestException as exc:
        messages.error(request, f"No se pudo contactar a Google: {exc}")
        return redirect("patients:admin_panel")

    access_token = payload.get("access_token")
    if not access_token:
        messages.error(request, "Google no devolvió un token de acceso.")
        return redirect("patients:admin_panel")

    google_email = ""
    try:
        info_resp = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        if info_resp.status_code == 200:
            google_email = info_resp.json().get("email", "")
    except requests.RequestException:
        pass

    expires_in = int(payload.get("expires_in", 3600))
    expires_at = timezone.now() + timedelta(seconds=expires_in)
    refresh_token = payload.get("refresh_token", "")
    creds, created = GoogleCalendarCredentials.objects.get_or_create(
        user=request.user,
        defaults={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": payload.get("token_type", "Bearer"),
            "expires_at": expires_at,
            "google_email": google_email,
        },
    )
    if not created:
        creds.access_token = access_token
        creds.refresh_token = refresh_token or creds.refresh_token
        creds.token_type = payload.get("token_type", "Bearer")
        creds.expires_at = expires_at
        creds.google_email = google_email
        creds.save()

    messages.success(request, "Google Calendar se conectó correctamente.")
    return redirect("patients:admin_panel")


@user_passes_test(lambda u: u.is_staff)
def disconnect_google_calendar(request):
    """Desconecta Google Calendar (borra las credenciales guardadas)."""
    GoogleCalendarCredentials.objects.filter(user=request.user).delete()
    messages.info(request, "Se desconectó Google Calendar.")
    return redirect("patients:admin_panel")


# ──────────────────────────────────────────────────────
# BANDEJA DE ENTRADA: Consultas desde la web
# ──────────────────────────────────────────────────────

LEADS_PER_PAGE = 20


@user_passes_test(lambda u: u.is_staff)
def lead_inbox(request):
    """Lista paginada de leads con filtros por status, fuente, búsqueda y rango de fechas."""
    qs = Lead.objects.all()

    # Filtro por estado
    status_filter = request.GET.get("status", "")
    if status_filter in dict(Lead.Status.choices):
        qs = qs.filter(status=status_filter)

    # Filtro por fuente
    source_filter = request.GET.get("source", "")
    if source_filter:
        qs = qs.filter(source=source_filter)

    # Búsqueda por texto
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(message__icontains=search_query)
        )

    # Filtro por rango de fechas
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    if date_from:
        d = parse_date(date_from)
        if d:
            qs = qs.filter(created_at__date__gte=d)
    if date_to:
        d = parse_date(date_to)
        if d:
            qs = qs.filter(created_at__date__lte=d)

    # Contadores para los filtros (sobre queryset completo sin paginación)
    base_qs = Lead.objects.all()
    status_counts = {
        "all": base_qs.count(),
        "new": base_qs.filter(status=Lead.Status.NEW).count(),
        "read": base_qs.filter(status=Lead.Status.READ).count(),
        "replied": base_qs.filter(status=Lead.Status.REPLIED).count(),
        "archived": base_qs.filter(status=Lead.Status.ARCHIVED).count(),
    }

    # Paginación
    from django.core.paginator import Paginator

    paginator = Paginator(qs, LEADS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "leads": page_obj,
        "status_counts": status_counts,
        "current_status": status_filter,
        "current_source": source_filter,
        "search_query": search_query,
        "date_from": date_from,
        "date_to": date_to,
        "source_choices": Lead.objects.values_list("source", flat=True).distinct(),
    }
    return render(request, "patients/lead_inbox.html", context)


@user_passes_test(lambda u: u.is_staff)
def lead_detail(request, pk):
    """Detalle de un lead + historial de respuestas + formulario reply."""
    lead = get_object_or_404(Lead, pk=pk)

    # Marcar como leído si estaba nuevo
    if not lead.is_read:
        lead.is_read = True
        if lead.status == Lead.Status.NEW:
            lead.status = Lead.Status.READ
        lead.save(update_fields=["is_read", "status", "updated_at"])

    replies = lead.replies.select_related("sent_by").all()
    form = LeadReplyForm()

    context = {
        "lead": lead,
        "replies": replies,
        "form": form,
    }
    return render(request, "patients/lead_detail.html", context)


@user_passes_test(lambda u: u.is_staff)
@require_POST
def lead_reply(request, pk):
    """Envía una respuesta a un lead."""
    lead = get_object_or_404(Lead, pk=pk)
    form = LeadReplyForm(request.POST)

    if form.is_valid():
        reply = form.save(commit=False)
        reply.lead = lead
        reply.sent_by = request.user
        reply.save()

        lead.reply_count = lead.replies.count()
        lead.status = Lead.Status.REPLIED
        lead.save(update_fields=["reply_count", "status", "updated_at"])

        messages.success(request, "Respuesta enviada correctamente.")
    else:
        messages.error(request, "Hubo un error al enviar la respuesta.")

    return redirect("patients:lead_detail", pk=pk)


@user_passes_test(lambda u: u.is_staff)
@require_POST
def lead_update_status(request, pk):
    """Cambiar el estado de un lead."""
    lead = get_object_or_404(Lead, pk=pk)
    new_status = request.POST.get("status", "")

    if new_status in dict(Lead.Status.choices):
        lead.status = new_status
        if new_status in (Lead.Status.READ, Lead.Status.REPLIED, Lead.Status.ARCHIVED):
            lead.is_read = True
        lead.save(update_fields=["status", "is_read", "updated_at"])
        messages.success(request, f"Estado cambiado a {lead.get_status_display()}.")
    else:
        messages.error(request, "Estado no válido.")

    return redirect("patients:lead_detail", pk=pk)


@user_passes_test(lambda u: u.is_staff)
@require_POST
def lead_delete(request, pk):
    """Eliminar un lead y todas sus respuestas."""
    lead = get_object_or_404(Lead, pk=pk)
    lead_name = lead.name
    lead.delete()
    messages.success(request, f"Consulta de {lead_name} eliminada.")
    return redirect("patients:lead_inbox")


@user_passes_test(lambda u: u.is_staff)
@require_POST
def lead_mark_all_read(request):
    """Marca todos los leads nuevos como leídos."""
    updated = Lead.objects.filter(is_read=False).update(
        is_read=True, status=Lead.Status.READ
    )
    messages.success(request, f"{updated} consulta(s) marcada(s) como leída(s).")
    return redirect("patients:lead_inbox")
