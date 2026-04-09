from odoo.addons.web.controllers.home import SIGN_UP_REQUEST_PARAMS
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.http import request
from odoo import http


class CustomWebLogin(AuthSignupHome):

    def _apply_login_page_settings(self):
        SIGN_UP_REQUEST_PARAMS.add("login_page_design")
        SIGN_UP_REQUEST_PARAMS.add("login_page_custom_background")
        SIGN_UP_REQUEST_PARAMS.add("login_page_show_motto")
        SIGN_UP_REQUEST_PARAMS.add("login_page_motto_text")
        SIGN_UP_REQUEST_PARAMS.add("login_page_motto_text_color")

        params = request.env["ir.config_parameter"].sudo()
        request.params["login_page_design"] = params.get_param("custom_login.login_page_design")
        request.params["login_page_custom_background"] = params.get_param("custom_login.custom_background")
        request.params["login_page_show_motto"] = params.get_param("custom_login.login_page_show_motto")
        request.params["login_page_motto_text_color"] = params.get_param("custom_login.login_page_motto_text_color")
        request.params["login_page_motto_text"] = params.get_param("custom_login.login_page_motto_text")
        request.params["login_page_motto_author"] = params.get_param("custom_login.login_page_motto_author")
        if not request.params["login_page_motto_text_color"]:
            request.params["login_page_motto_text_color"] = "#000000"

    @http.route("/web/login", type="http", auth="public", website=True, sitemap=False)
    def web_login(self, redirect=None, **kw):
        self._apply_login_page_settings()
        response = super().web_login(redirect=redirect, **kw)

        return response

    @http.route("/web/reset_password", type="http", auth="public", website=True, sitemap=False)
    def web_auth_reset_password(self, *args, **kw):
        self._apply_login_page_settings()
        return super().web_auth_reset_password(*args, **kw)

    @http.route("/web/signup", type="http", auth="public", website=True, sitemap=False)
    def web_auth_signup(self, *args, **kw):
        self._apply_login_page_settings()
        return super().web_auth_signup(*args, **kw)
