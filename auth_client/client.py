import json
import time
import traceback
import urllib
from django.conf import settings
import requests

# from accounts.utils import Address


def process(method='get'):  # pragma: no cover
    request_method = method

    def dec_wrapper(func):
        def wrapper(self, **kwargs):
            url = self.uri + self.endpoint + self.edge + '/'
            header = {'TOKEN': ''}
            header = header.update({self.header_key: self.token}) if self.token else header
            params = kwargs
            request_route = requests.post if request_method == 'post' else requests.get
            response = request_route(url=url, data=params, headers=header)
            kwargs['response'] = response
            return func(self, **kwargs)

        return wrapper

    return dec_wrapper


def require(params):  # pragma: no cover
    def dec_wrapper(func):
        def func_wrapper(self, **kwargs):
            for param in params:
                if param not in kwargs.keys():
                    raise KeyError("'{param}' is required to call {func}".format(param=param, func=func.__name__))
            return func(self, **kwargs)

        return func_wrapper

    return dec_wrapper


class PriyoClient(object):  # pragma: no cover
    def __init__(self, api_key, raise_on_error_status=False):
        # self.uri = 'http://127.0.0.1:8010'
        self.uri = settings.AUTH_API_BASE
        self.endpoint = '/accounts'
        self.edge = ''
        self.header_key = 'TOKEN'
        self.api_key_header = 'APIKEY'
        self.token_key = 'Authorization'
        self.api_key = api_key
        self.token = ''
        self.params = {}
        self.get_params = None
        self.raise_on_error_status = raise_on_error_status

    def add_token(self, token):
        self.token = token
        return self

    def __remote_call(self, method, token):
        url = self.uri + self.endpoint + self.edge + '/'
        headers = {
            self.api_key_header: self.api_key,
            "Content-Type": "application/json",
        }

        if method.upper() == 'GET' and self.get_params:
            q_params = urllib.parse.urlencode(self.get_params)
            url += "?"+q_params
            self.get_params = None

        if token:
            headers[self.token_key] = "Token "+str(token)
        # print(url)
        payload = json.dumps(self.params, default=str)
        response = requests.request(method.upper(), url, data=payload, headers=headers)

        if self.raise_on_error_status:
            response.raise_for_status()

        response_json = response.json()
        if type(response_json) is dict:
            response_json.update({'status_code': response.status_code})
        else:
            response_json = {'data': response.json(), 'status_code': response.status_code}
        return response_json

    # @require(['mobile'])
    # @process('post')
    def register(self, **kwargs):
        self.endpoint = '/accounts'
        self.edge = '/registration'
        self.params = kwargs
        response = self.__remote_call('post')
        return response

    # @require(['mobile'])
    # @process('post')
    def login(self, **kwargs):
        self.endpoint = '/auth/api/v1'
        self.edge = '/login'
        self.params = kwargs
        return self.__remote_call('post', self.token)

    def logout(self, token):
        self.endpoint = '/auth/api/v1'
        self.edge = '/logout'
        return self.__remote_call('post', token)

    def get_profile(self, token):
        self.endpoint = '/auth/api/v1'
        self.edge = '/user-profile'
        return self.__remote_call('get', token)

    def profile_update(self, token, **kwargs):
        self.endpoint = '/auth/api/v1'
        self.edge = '/update-user-profile'
        self.params = kwargs
        return self.__remote_call('put', token)

    @require(['password'])
    # @process('post')
    def set_password(self, **kwargs):
        self.endpoint = '/accounts'
        self.edge = '/set-password'
        self.params = kwargs
        return self.__remote_call('post')

    @require(['token'])
    # @process('get')
    def is_authenticated(self, **kwargs):
        self.endpoint = '/accounts'
        self.edge = '/status'
        self.token = kwargs.get('token')
        return self.__remote_call('get')

    def get_user_profile_by_uuid(self, uuid):
        try:
            self.endpoint = ''
            self.edge = '/auth/api/v1/user-profile-by-uid'
            self.get_params = {"uid": uuid}
            response = self.__remote_call('get', None)
            if response['status_code'] == 200:
                return response
            return None
        except Exception as e:
            traceback.print_exc()
            return None

    def get_profile_summary_by_uuid(self, uuid):
        profile = self.get_user_profile_by_uuid(uuid=uuid)
        if profile and profile.get('is_active', False):
            return {
                "name": profile['profile']['name'],
                "mobile": profile['mobile'],
                "id": profile['id'],
                "uid": uuid,
                "image": profile['profile']['image']
            }
        return None


    def get_other_user_profile_by_uuid(self, uuid, token):
        try:
            self.endpoint = ''
            self.edge = '/auth/api/v1/other-user-profile-by-uid/summary'
            self.get_params = {"uid": uuid}
            response = self.__remote_call('get', token)
            if response['status_code'] == 200:
                return response
            return None
        except Exception as e:
            traceback.print_exc()
            return None

    def get_user_by_mobile(self, mobile, token):
        self.endpoint = ''
        self.edge = '/auth/api/v1/other-user-profile-by-phone'
        self.get_params = {"mobile": mobile}
        response = self.__remote_call('get', token=token)
        if response['status_code'] == 200:
            return response
        return None


    def verify_token(self, token):
        try:
            self.endpoint = ''
            self.edge = '/auth/api/v1/verify-token'
            return self.__remote_call('GET', token)
        except Exception as e:
            print(e)
            return None

    def create_address(self, token, **kwargs):
        self.endpoint = '/auth/api/v1'
        self.edge = '/address'
        kwargs['address_type'] = 'shipping'
        self.data = kwargs
        return self.__remote_call('post', token)

    def update_address(self,token, address_id, **kwargs):
        self.endpoint = '/auth/api/v1'
        self.edge = '/address/{}'.format(address_id)
        self.params = kwargs
        return self.__remote_call('put', token)

    def update_mobile(self, token,  **kwargs):
        self.endpoint = '/auth/api/v1'
        self.edge = '/update-email-phone'
        self.params = kwargs
        response = self.__remote_call('post', token)
        return response

    def upload_image(self, token,  image):
        headers = {
            self.token_key: "token {}".format(token),
            self.api_key_header: self.api_key
        }
        image_upload_response = requests.post("{}/auth/api/v1/file-upload/".format(settings.AUTH_API_BASE),
                                              files={'file': (image.name, image)},
                                              headers=headers)
        if not image_upload_response.status_code == 201:
            raise Exception("Exception in uploading image")

        return image_upload_response

    def selective_profile_update(self, token, profile_field_group, post_data, image=None):
        post_data = post_data

        profile_field_group_map = {
            "basic_info": ['name', 'organization', 'gender', 'dob'],
            "image": ['image'],
            "address": ['address'],
            "mobile": ['mobile']

        }

        if profile_field_group == "basic_info":
            request_data = {}
            for field in profile_field_group_map['basic_info']:
                request_data[field] = post_data[field]
            self.profile_update(token, **request_data)

        elif profile_field_group == 'image':
            if image:
                image_upload_response = self.upload_image(token, image)
                self.profile_update(token, **{'image': json.loads(image_upload_response.text)['file']})
        # elif profile_field_group == 'address':
        #     shipping_address = Address(address_data=post_data)
        #     if shipping_address.id == -1:
        #         self.create_address(token, **shipping_address.to_dict())
        #     else:
        #         self.update_address(token, address_id=shipping_address.id, **shipping_address.to_dict())
        elif profile_field_group == 'mobile':
            mobile_other_part = post_data['mobile']
            if post_data['mobile'].startswith('0'):
                mobile_other_part = mobile_other_part.lstrip('0')
            mobile = post_data['country_code'] + mobile_other_part
            response = self.update_mobile(token, **{'mobile': mobile})
            if response['status_code'] != 200:
                if response['status_code'] == 400 and 'non_field_errors' in response:
                    return False, response['non_field_errors'][0]
                elif response['status_code'] == 400 and response.get('data', None) and type(response['data']) is list:
                    return False, ', '.join(response['data'])
                else:
                    return False, 'Something went wrong, please try again'

        return True, 'Successful'