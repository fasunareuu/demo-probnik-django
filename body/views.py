from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import LoginForm, OrderForm, ProductForm
from .models import Order, Product, Supplier, User


def login_view(request):
    if request.user.is_authenticated:
        return redirect("product_list")

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect("product_list")

    return render(request, "store/login.html", {"form": form})


def guest_login_view(request):
    guest_user, created = User.objects.get_or_create(
        username="guest",
        defaults={
            "full_name": "Гость",
            "is_active": True,
        },
    )
    if created:
        guest_user.set_unusable_password()
        guest_user.save()

    login(request, guest_user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("product_list")


def logout_view(request):
    """Выход из системы."""
    logout(request)
    return redirect("login")


@login_required
def product_list(request):
    products = Product.objects.select_related(
        "category", "manufacturer", "supplier"
    ).all()
    suppliers = Supplier.objects.all()

    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(article__icontains=query)
            | Q(description__icontains=query)
        )

    supplier_id = request.GET.get("supplier", "")
    if supplier_id:
        products = products.filter(supplier_id=supplier_id)

    sort = request.GET.get("sort", "")
    if sort == "stock_asc":
        products = products.order_by("stock")
    elif sort == "stock_desc":
        products = products.order_by("-stock")
    else:
        products = products.order_by("name")

    context = {
        "products": products,
        "suppliers": suppliers,
        "query": query,
        "selected_supplier": supplier_id,
        "sort": sort,
    }
    return render(request, "store/product_list.html", context)


@login_required
def product_add(request):
    if not request.user.can_edit_products():
        messages.error(
            request, "Доступ запрещён. Только администратор может добавлять товары."
        )
        return redirect("product_list")

    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Товар успешно добавлен.")
        return redirect("product_list")

    return render(
        request,
        "store/product_form.html",
        {
            "form": form,
            "title": "Добавить товар",
            "is_edit": False,
        },
    )


@login_required
def product_edit(request, pk):
    if not request.user.can_edit_products():
        messages.error(
            request, "Доступ запрещён. Только администратор может редактировать товары."
        )
        return redirect("product_list")

    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Товар «{product.name}» обновлён.")
        return redirect("product_list")

    form.fields["article"].widget.attrs["readonly"] = True

    return render(
        request,
        "store/product_form.html",
        {
            "form": form,
            "title": f"Редактировать: {product.name}",
            "product": product,
            "is_edit": True,
        },
    )


@login_required
def product_delete(request, pk):
    if not request.user.can_edit_products():
        messages.error(request, "Доступ запрещён.")
        return redirect("product_list")

    product = get_object_or_404(Product, pk=pk)

    orders_count = Order.objects.filter(article=product.article).count()
    if orders_count > 0:
        messages.error(
            request,
            f"Нельзя удалить товар «{product.name}»: он используется в {orders_count} заказ(ах).",
        )
        return redirect("product_list")

    if request.method == "POST":
        name = product.name
        product.delete()
        messages.success(request, f"Товар «{name}» удалён.")
        return redirect("product_list")

    return render(request, "store/product_confirm_delete.html", {"product": product})


@login_required
def order_list(request):
    if not request.user.can_view_orders():
        messages.error(request, "Доступ запрещён.")
        return redirect("product_list")

    orders = Order.objects.select_related("delivery_point", "client").all()

    query = request.GET.get("q", "").strip()
    if query:
        orders = orders.filter(
            Q(client_name__icontains=query)
            | Q(number__icontains=query)
            | Q(article__icontains=query)
        )

    return render(
        request,
        "store/order_list.html",
        {
            "orders": orders,
            "query": query,
        },
    )


@login_required
def order_edit(request, pk):
    if not request.user.can_edit_orders():
        messages.error(
            request, "Доступ запрещён. Только администратор может редактировать заказы."
        )
        return redirect("order_list")

    order = get_object_or_404(Order, pk=pk)
    form = OrderForm(request.POST or None, instance=order)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Заказ №{order.number} обновлён.")
        return redirect("order_list")

    form.fields["number"].widget.attrs["readonly"] = True

    return render(
        request,
        "store/order_form.html",
        {
            "form": form,
            "order": order,
            "title": f"Редактировать заказ №{order.number}",
        },
    )


@login_required
def order_delete(request, pk):
    if not request.user.can_edit_orders():
        messages.error(request, "Доступ запрещён.")
        return redirect("order_list")

    order = get_object_or_404(Order, pk=pk)

    if request.method == "POST":
        num = order.number
        order.delete()
        messages.success(request, f"Заказ №{num} удалён.")
        return redirect("order_list")

    return render(request, "store/order_confirm_delete.html", {"order": order})
