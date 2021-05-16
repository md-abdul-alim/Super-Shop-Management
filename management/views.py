import requests  # to get image from the web
from supershop import settings
import shutil  # to save it locally
import json
import os
import random
import string
import mimetypes

import uuid
import stripe
# Create your views here.
# payment link: https://stripe.com/docs/api/charges/create?lang=python
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, JsonResponse, request, response
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView, View
from django.template.loader import render_to_string, get_template
from .forms import CheckoutForm, CouponForm, PaymentForm, RefundForm
from .models import (Address, Coupon, Item, Order, OrderItem, Payment, Refund,
                     UserProfile)
import pdfkit
stripe.api_key = settings.STRIPE_SECRET_KEY
# "sk_test_4eC39HqLyjWDarjtT1zdp7dc"
# `source` is obtained with Stripe.js; see https://stripe.com/docs/payments/accept-a-payment-charges#web-create-token


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


def is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False
    return valid


def products(request):
    items = Item.objects.all()
    content = {
        'items': items
    }
    return render(request, "products.html", content)


@login_required(login_url='login')
def search_expenses(request):
    if request.method == 'POST':
        search_str = json.loads(request.body).get('searchText')
        items = Item.objects.filter(
            title__icontains=search_str) | Item.objects.filter(
            price__icontains=search_str) | Item.objects.filter(
            current_stock__istartswith=search_str) | Item.objects.filter(
            id__istartswith=search_str)
        data = items.values()
        return JsonResponse(list(data), safe=False)


class HomeView(ListView):
    model = Item
    paginate_by = 4
    template_name = "home.html"


def invoice_view(request, ref_code):
    order_obj = Order.objects.get(ref_code=ref_code)
    print(order_obj)
    context = {
        "order_object": order_obj.ref_code
    }
    return render(request, 'invoice.html', context)


def qr_code_invoice_view(request, ref_code):
    order_obj = Order.objects.get(ref_code=ref_code)
    print(order_obj.qr_invoice.url)
    context = {
        "order_object": order_obj
    }
    return render(request, 'qr_code_invoice_view.html', context)


def invoice_QR_download(request, ref_code):
    '''
        https://towardsdatascience.com/how-to-download-an-image-using-python-38a75cfa21c
        https://stackoverflow.com/questions/36392510/django-download-a-file/36394206
        https://www.w3schools.com/tags/att_a_download.asp
    '''
    ord_obj = Order.objects.get(ref_code=ref_code)
    # image_url = "http://127.0.0.1:8000/media/qr_codes/qr-301eb5e1-188d-4577-acac-8947437a1ad9.png"
    image_url = "http://127.0.0.1:8000/media/"+str(ord_obj.qr_invoice)
    #image_url = "http://supershopmanagement.herokuapp.com/media/"+str(ord_obj.qr_invoice)

    # Open the url image, set stream to True, this will return the stream content.
    r = requests.get(image_url, stream=True)

    #filename = image_url.split("/")[-1]
    # filename = image_url.split("/")[5]
    # OR
    # for security issue we will generate new name for qr code.
    filename = 'qr-' + str(uuid.uuid4()) + '.png'
    response = HttpResponse(r, content_type="image/png")
    response['Content-Disposition'] = "attachment; filename=%s" % filename
    return response


def pdf_invoice_view(request, ref_code):

    try:
        order = Order.objects.get(
            user=request.user, ordered=True, ref_code=ref_code)
        context = {
            'object': order
        }
        return render(request, 'pdf_invoice_view.html', context)
    except ObjectDoesNotExist:
        messages.warning(request, "You do not have an pdf invoice")
        return redirect("/")

    # order_obj = Order.objects.get(ref_code = ref_code)
    # print(order_obj.qr_invoice.url)
    # context = {
    #     "order_object": order_obj
    # }
    # return render(request, 'pdf_invoice_view.html', context)


def pdf_invoice_download(self, ref_code):
    template = get_template('pdf_download.html')
    object = Order.objects.get(ordered=True, ref_code=ref_code)
    print(object.ref_code)

    html = template.render(
        {'object': object, 'MEDIA_BUCKET_URL_PREFIX': settings.MEDIA_BUCKET_URL_PREFIX})
    options = {
        'page-size': "A4",
        'encoding': "UTF-8",
        # "enable-local-file-access": None,
        "viewport-size": "1024x768",
    }

    ####################
    # https://stackoverflow.com/questions/54707110/how-to-get-wkhtmltopdf-working-on-heroku
    import os
    import sys
    import subprocess
    import platform

    if platform.system() == "Windows":
        pdfkit_config = pdfkit.configuration(wkhtmltopdf=os.environ.get(
            'WKHTMLTOPDF_BINARY', 'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'))
    elif platform.system() == "Linux":
        pdfkit_config = pdfkit.configuration(wkhtmltopdf=os.environ.get(
            'WKHTMLTOPDF_BINARY', '/usr/bin/wkhtmltopdf')) #https://www.odoo.com/forum/help-1/unable-to-find-wkhtmltopdf-on-this-system-the-report-will-be-shown-in-html-63900
    else:
        os.environ['PATH'] += os.pathsep + os.path.dirname(sys.executable)
        WKHTMLTOPDF_CMD = subprocess.Popen(['which', os.environ.get('WKHTMLTOPDF_BINARY', 'wkhtmltopdf')],
                                           stdout=subprocess.PIPE).communicate()[0].strip()
        pdfkit_config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_CMD)

    pdf_invoice = pdfkit.from_string(
        html, False, options=options, configuration=pdfkit_config)
    ####################
    # OR: only for linux
    # pdf_invoice = pdfkit.from_string(html, False, options=options)
    filename = 'pdf-invoice-' + str(uuid.uuid4()) + '.pdf'
    response = HttpResponse(pdf_invoice, content_type="application/pdf")
    response['Content-Disposition'] = "attachment; filename=%s" % filename
    return response


class ItemDetailView(DetailView):
    model = Item
    template_name = "product.html"


@login_required(login_url='login')
def product_delete(request, id):
    item = Item.objects.get(pk=id)
    item.delete()
    messages.success(request, 'Product Deleted')
    return redirect("ecommerce:home")


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )

    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            if order_item.quantity+1 > item.current_stock:
                messages.info(
                    request, "This item quantity reached it's limit!")
                return redirect("ecommerce:order-summary")
            else:
                order_item.quantity += 1
                order_item.save()
                messages.info(request, "This item quantity was updated!")
                return redirect("ecommerce:order-summary")
        else:
            order.items.add(order_item)
            # this part is working
            messages.info(request, "This item was added to your cart.")
            return redirect("ecommerce:order-summary")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "This item was added to your cart.")
        return redirect("ecommerce:order-summary")


@login_required
def remove_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            # order.items.remove(order_item)
            order_item.delete()
            order_obj = Order.objects.filter(
                user=request.user,
                ordered=False
            )[0]
            # TODO manytomany field data count done
            if order_obj.items.count() == 0:
                order_obj.delete()
            messages.info(request, "This item was removed from your cart.")
            return redirect("ecommerce:order-summary")
        else:
            messages.info(request, "This item was not in your cart.")
            return redirect("ecommerce:product", slug=slug)
    else:
        messages.info(request, "You do not have an active order.")
        return redirect("ecommerce:product", slug=slug)


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                # order.items.remove(order_item)
                order_item.delete()
            messages.info(request, "This item quantit was updated.")
            return redirect("ecommerce:order-summary")
        else:
            # add a message saying the user doesnot have an order
            messages.info(request, "This item was not in your cart.")
            return redirect("ecommerce:product", slug=slug)
    else:
        # add a message saying the user doesnot have an order
        messages.info(request, "You do not have an active order.")
        return redirect("ecommerce:product", slug=slug)


class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order")
            return redirect("/")


class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            form = CheckoutForm()
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True
            }

            shipping_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='S',
                default=True
            )
            if shipping_address_qs.exists():
                context.update(
                    {'default_shipping_address': shipping_address_qs[0]})

            billing_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='B',
                default=True
            )
            if billing_address_qs.exists():
                context.update(
                    {'default_billing_address': billing_address_qs[0]})

            return render(self.request, "checkout.html", context)
        except ObjectDoesNotExist:
            messages.info(self.request, "You do not have an active order")
            return redirect("ecommerce:checkout")

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            # print(self.request.POST)
            if form.is_valid():
                #-------------------Shipping address part-----------------------------------#
                use_default_shipping = form.cleaned_data.get(
                    'use_default_shipping')
                if use_default_shipping:
                    print("Using the default shipping address")
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='S',
                        default=True
                    )

                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.info(
                            self.request, "No default shipping address available")
                        return redirect('ecommerce:checkout')
                else:
                    print("User is entering a new shipping address")
                    shipping_address1 = form.cleaned_data.get(
                        'shipping_address')
                    shipping_address2 = form.cleaned_data.get(
                        'shipping_address2')
                    shipping_country = form.cleaned_data.get(
                        'shipping_country')
                    shipping_zip = form.cleaned_data.get('shipping_zip')
                    # TODO: add functionality for these fields

                    if is_valid_form([shipping_address1, shipping_country, shipping_zip]):
                        shipping_address = Address(
                            user=self.request.user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            country=shipping_country,
                            zip=shipping_zip,
                            address_type='S'
                        )
                        shipping_address.save()

                        order.shipping_address = shipping_address
                        order.save()

                        set_default_shipping = form.cleaned_data.get(
                            'set_default_shipping')
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save()

                    else:
                        messages.info(
                            self.request, "Please fill in the required shipping address fields")

                #-------------------billing address part-----------------------------------#

                same_billing_address = form.cleaned_data.get(
                    'same_billing_address')
                use_default_billing = form.cleaned_data.get(
                    'use_default_billing')
                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.pk = None
                    billing_address.save()
                    billing_address.address_type = 'B'
                    billing_address.save()
                    order.billing_address = billing_address
                    order.save()

                elif use_default_billing:
                    print("Using the default billing address")
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='B',
                        default=True
                    )

                    if address_qs.exists():
                        billing_address = address_qs[0]
                        order.billing_address = billing_address
                        order.save()
                    else:
                        messages.info(
                            self.request, "No default billing address available")
                        return redirect('ecommerce:checkout')
                else:
                    print("User is entering a new billing address")
                    billing_address1 = form.cleaned_data.get(
                        'billing_address')
                    billing_address2 = form.cleaned_data.get(
                        'billing_address2')
                    billing_country = form.cleaned_data.get(
                        'billing_country')
                    billing_zip = form.cleaned_data.get('billing_zip')

                    if is_valid_form([billing_address1, billing_country, billing_zip]):
                        billing_address = Address(
                            user=self.request.user,
                            street_address=billing_address1,
                            apartment_address=billing_address2,
                            country=billing_country,
                            zip=billing_zip,
                            address_type='B'
                        )
                        billing_address.save()

                        order.billing_address = billing_address
                        order.save()

                        set_default_billing = form.cleaned_data.get(
                            'set_default_billing')
                        if set_default_billing:
                            billing_address.default = True
                            billing_address.save()

                    else:
                        messages.info(
                            self.request, "Please fill in the required billing address fields")
                #-------------------billing address part end-------------------------------#
                payment_option = form.cleaned_data.get('payment_option')

                if payment_option == 'S':
                    return redirect('ecommerce:payment')
                elif payment_option == 'P':
                    return redirect('ecommerce:payment')
                elif payment_option == 'N':
                    return redirect('ecommerce:payment')
                elif payment_option == 'B':
                    return redirect('ecommerce:payment')
                elif payment_option == 'R':
                    return redirect('ecommerce:payment')
                else:
                    messages.warning(
                        self.request, "Invalid payment option selected")
                    return redirect('ecommerce:checkout')

        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order")
            return redirect("ecommerce:order-summary")


class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False,
                'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY
            }
            # https://stackoverflow.com/questions/36317816/relatedobjectdoesnotexist-user-has-no-userprofile
            userprofile, created = UserProfile.objects.get_or_create(
                user=self.request.user)

            return render(self.request, "payment.html", context)
        else:
            messages.warning(
                self.request, "You have not added a billing address")
            return redirect("ecommerce:checkout")

    # details about decoupling: https://pypi.org/project/python-decouple/
    # FOLLOW THIS LINK FOR decouple setup : https://www.youtube.com/watch?v=NRf1LeQju2g&ab_channel=ProfessionalCipher
    def post(self, request):
        order = Order.objects.get(user=self.request.user, ordered=False)
        userprofile = UserProfile.objects.get(user=self.request.user)

        if request.method == 'POST':
            payment = Payment()
            payment.stripe_charge_id = self.request.POST['cardNumber']
            payment.user = self.request.user
            payment.amount = int(order.get_total() * 100)
            payment.save()

            userprofile.stripe_customer_id = self.request.POST['cardNumber']
            userprofile.one_click_purchasing = True
            userprofile.save()

            # assign the payment to the order
            # order item update. after payment order item will reset again from 0.
            order_items = order.items.all()
            order_items.update(ordered=True)
            for item in order_items:
                item.save()

            order.ordered = True
            order.payment = payment
            order.ref_code = create_ref_code()
            order.qr_code_invoice()
            order.save()

            messages.success(self.request, "Your order was successful!")
            return redirect("ecommerce:invoice", ref_code=order.ref_code)
            # return render(request, 'ecommerce:invoice',ref_id = order.ref_code)
            # error end
        else:
            messages.warning(self.request, "Invalid data received")
            return redirect("/")


class AddCouponView(View):
    def post(self, *args, **kwargs):
        if request.method == "POST":
            form = CouponForm(self.request.POST or None)
            if form.is_valid():
                try:
                    code = form.cleaned_data.get('code')
                    order = Order.objects.get(
                        user=self.request.user, ordered=False)
                    order.coupon = get_coupon(self.request, code)
                    order.save()
                    messages.success(self.request, "Successfully added coupon")
                    return redirect("ecommerce:checkout")

                except ObjectDoesNotExist:
                    messages.warning(
                        self.request, "You do not have an active order")
                    return redirect("ecommerce:checkout")


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')

            # edit the order
            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()
                # store the refund
                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()

                messages.info(self.request, "Your request was received.")
                return redirect("ecommerce:request-refund")
            except ObjectDoesNotExist:
                messages.info(self.request, "This order does not exist.")
                return redirect("ecommerce:request-refund")
