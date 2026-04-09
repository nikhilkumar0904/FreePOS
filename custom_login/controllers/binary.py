from odoo import http
from odoo.http import request, Response, _send_file
from odoo.tools import file_path 
from odoo.addons.web.controllers.binary import Binary
from odoo.tools.mimetypes import guess_mimetype
import base64
import io

class ThemeBinary(Binary):
    @http.route(
        [
            '/web/binary/login_page_background_image',
            '/web/login_page_background_image',
            '/login_page_background_image.png',

        ], type='http', auth="none", cors="*"
    )
    def login_page_background_image(self, **kw):
        param_obj = request.env['ir.config_parameter'].sudo()
        background_img = param_obj.get_param('custom_login.login_page_background_image')


        if background_img:
            imgname ='background'
            imgext = '.png'

            image_base64 = base64.b64decode(background_img)
            image_data = io.BytesIO(image_base64)
            mimetype = guess_mimetype(image_base64, default='image/png')
            imgext = '.' + mimetype.split('/')[1]
            if imgext == '.svg+xml':
                imgext = 'svg'
            response = _send_file(
                image_data,
                request.httprequest.environ, 
                download_name = imgname + imgext,
                mimetype =mimetype,
                response_class =Response,

            )
        else:
            response = http.Stream.from_path(file_path('custom_login/static/img/login_logo.png')).get_response()
        return response
        
    @http.route (
        [
            '/web/binary/login_logo',
            '/web/login_logo',
            '/login_logo.png',
        ],type='http', auth="none", cors="*"
    )
        
    def login_page_logo(self, **kw):
        param_obj = request.env['ir.config_parameter'].sudo()
        logo_img= param_obj.get_param('custom_login.login_page_logo')

        if logo_img:
            imgname = 'logo'
            imgext = '.png'

            image_base64 = base64.b64decode(logo_img)
            image_data = io.BytesIO(image_base64)
            mimetype = guess_mimetype(image_base64, default='image/png')
            imgext = '.' + mimetype.split('/')[1]
            if imgext =='.svg+xml':
                imgext = '.svg'
            
            response = _send_file(
                image_data,
                request.httprequest.environ,
                download_name=imgname + imgext, 
                mimetype = mimetype, 
                response_class = Response, 
            )

        else:
            response = http.Stream.from_path(file_path('custom_login/static/img/login_logo.png')).get_response()
        
        return response

    