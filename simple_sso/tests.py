# -*- coding: utf-8 -*-
from django.contrib.auth import get_user
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.test.client import Client as TestClient
from django.test.testcases import TestCase
from simple_sso.sso_server.models import Client, Token
from simple_sso.test_utils.context_managers import (SettingsOverride, 
    UserLoginContext)
from simple_sso.utils import SIMPLE_KEYS
import urlparse

class SimpleSSOTests(TestCase):
    def setUp(self):
        import requests
        def get(url, params={}, headers={}, cookies=None, auth=None, **kwargs):
            testclient = TestClient()
            return testclient.get(url, params)
        requests.get = get
    
    def test_walkthrough(self):
        # create a user and a client
        USERNAME = PASSWORD = 'myuser'
        server_user = User.objects.create_user(USERNAME, 'my@user.com', PASSWORD)
        client = Client.objects.create(root_url='/client/')
        with SettingsOverride(SIMPLE_SSO_KEY=client.key, SIMPLE_SSO_SECRET=client.secret):
            # verify theres no tokens yet
            self.assertEqual(Token.objects.count(), 0)
            response = self.client.get(reverse('simple-sso-login'))
            # there should be a token now
            self.assertEqual(Token.objects.count(), 1)
            # this should be a HttpResponseRedirect
            self.assertEqual(response.status_code, HttpResponseRedirect.status_code)
            # check that it's the URL we expect
            url = urlparse.urlparse(response['Location']) 
            path = url.path
            self.assertEqual(path, reverse('simple-sso-authorize'))
            # follow that redirect
            response = self.client.get(response['Location'])
            # now we should have another redirect to the login
            self.assertEqual(response.status_code, HttpResponseRedirect.status_code)
            # check that the URL is correct
            url = urlparse.urlparse(response['Location']) 
            path = url.path
            self.assertEqual(path, reverse('django.contrib.auth.views.login'))
            # follow that redirect
            login_url = response['Location']
            response = self.client.get(login_url)
            # now we should have a 200
            self.assertEqual(response.status_code, HttpResponse.status_code)
            # and log in using the username/password from above
            response = self.client.post(login_url, {'username': USERNAME, 'password': PASSWORD})
            # now we should have a redirect back to the authorize view
            self.assertEqual(response.status_code, HttpResponseRedirect.status_code)
            # check that it's the URL we expect
            url = urlparse.urlparse(response['Location']) 
            path = url.path
            self.assertEqual(path, reverse('simple-sso-authorize'))
            # follow that redirect
            response = self.client.get(response['Location'])
            # this should again be a redirect
            self.assertEqual(response.status_code, HttpResponseRedirect.status_code)
            # this time back to the client app, confirm that!
            url = urlparse.urlparse(response['Location']) 
            path = url.path
            self.assertEqual(path, reverse('simple-sso-authenticate'))
            # follow it again
            response = self.client.get(response['Location'])
            # again a redirect! This time to /
            url = urlparse.urlparse(response['Location']) 
            path = url.path
            self.assertEqual(path, reverse('root'))
            # if we follow to root now, we should be logged in
            response = self.client.get(response['Location'])
            client_user = get_user(self.client)
            self.assertEqual(client_user.password, '!')
            self.assertNotEqual(server_user.password, '!')
            for key in SIMPLE_KEYS:
                self.assertEqual(getattr(client_user, key), getattr(server_user, key))
    
    def test_user_already_logged_in(self):
        # create a user and a client
        USERNAME = PASSWORD = 'myuser'
        server_user = User.objects.create_user(USERNAME, 'my@user.com', PASSWORD)
        client = Client.objects.create(root_url='/client/')
        with SettingsOverride(SIMPLE_SSO_KEY=client.key, SIMPLE_SSO_SECRET=client.secret):
            with UserLoginContext(self, server_user):
                # try logging in and auto-follow all 302s
                self.client.get(reverse('simple-sso-login'), follow=True)
                # check the user
                client_user = get_user(self.client)
                self.assertEqual(client_user.password, '!')
                self.assertNotEqual(server_user.password, '!')
                for key in SIMPLE_KEYS:
                    self.assertEqual(getattr(client_user, key), getattr(server_user, key))
                    
