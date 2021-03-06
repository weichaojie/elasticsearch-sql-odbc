#
# Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
# or more contributor license agreements. Licensed under the Elastic License;
# you may not use this file except in compliance with the Elastic License.
#

import pyodbc
import datetime
import hashlib

from elasticsearch import Elasticsearch
from data import TestData

CONNECT_STRING = 'Driver={Elasticsearch Driver};UID=elastic;PWD=%s;Secure=0;' % Elasticsearch.AUTH_PASSWORD

class Testing(object):

	_data = None

	def __init__(self, test_data):
		self._data = test_data

	def _reconstitute_csv(self, index_name):
		with pyodbc.connect(CONNECT_STRING) as cnxn:
			cnxn.autocommit = True
			csv = u""
			cols = self._data.csv_attributes(index_name)[1]
			fields = ",".join(cols)
			with cnxn.execute("select %s from %s" % (fields, index_name)) as curs:
				csv += u",".join(cols)
				csv += u"\n"
				for row in curs:
					vals = []
					for val in row:
						if val is None:
							val=""
						elif isinstance(val, datetime.datetime):
							val = val.isoformat() + "Z"
						vals.append(val)
					csv += u",".join(vals)
					csv += u"\n"

			return csv

	def _as_csv(self, index_name):
		csv = self._reconstitute_csv(index_name)

		md5 = hashlib.md5()
		md5.update(bytes(csv, "utf-8"))
		csv_md5 = self._data.csv_attributes(index_name)[0]
		if md5.hexdigest() != csv_md5:
			print("Reconstituded CSV of index '%s':\n%s" % (index_name, csv))
			raise Exception("reconstituted CSV differs from original for index '%s'" % index_name)

	def _count_all(self, index_name):
		cnt = 0
		with pyodbc.connect(CONNECT_STRING) as cnxn:
			cnxn.autocommit = True
			with cnxn.execute("select 1 from %s" % index_name) as curs:
				while curs.fetchone():
					cnt += 1
		csv_lines = self._data.csv_attributes(index_name)[2]
		if cnt != csv_lines:
			raise Exception("index '%s' only contains %s documents (vs original %s CSV lines)" %
					(index_name, cnt, csv_lines))

	def _clear_cursor(self, index_name):
		conn_str = CONNECT_STRING + ";MaxFetchSize=5"
		with pyodbc.connect(conn_str) as cnxn:
			cnxn.autocommit = True
			with cnxn.execute("select 1 from %s limit 10" % index_name) as curs:
				for i in range(3): # must be lower than MaxFetchSize, so no next page be requested
					curs.fetchone()
				# reuse the statment (a URL change occurs)
				with curs.execute("select 1 from %s" % index_name) as curs2:
					curs2.fetchall()
		# no exception raised -> passed

	def _current_user(self):
		with pyodbc.connect(CONNECT_STRING) as cnxn:
			cnxn.autocommit = True
			user = cnxn.getinfo(pyodbc.SQL_USER_NAME)
			if user != "elastic":
				raise Exception("current username not 'elastic': %s" % user)

	def perform(self):
		self._as_csv(TestData.LIBRARY_INDEX)
		self._as_csv(TestData.EMPLOYEES_INDEX)
		self._count_all(TestData.CALCS_INDEX)
		self._count_all(TestData.STAPLES_INDEX)
		self._clear_cursor(TestData.LIBRARY_INDEX)
		self._current_user()

		print("Tests successful.")

# vim: set noet fenc=utf-8 ff=dos sts=0 sw=4 ts=4 tw=118 :
