app_name = "stock_ops"
app_title = "Stock Ops"
app_publisher = "RMI"
app_description = "Mobile PWA for Material Request and Stock Entry"
app_email = "denzizzy966@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Tile di App Switcher (⊞) desk. route → Workspace desk; PWA tetap di /stock_ops.
add_to_apps_screen = [
	{
		"name": "stock_ops",
		"logo": "/assets/stock_ops/logo.png",
		"title": "Stock Ops",
		"route": "/app/stock-ops",
		"has_permission": "stock_ops.api.has_app_permission",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/stock_ops/css/stock_ops.css"
# app_include_js = "/assets/stock_ops/js/stock_ops.js"

# include js, css files in header of web template
# web_include_css = "/assets/stock_ops/css/stock_ops.css"
# web_include_js = "/assets/stock_ops/js/stock_ops.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "stock_ops/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {"Material Request": "public/js/material_request.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "stock_ops/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role) — user Stock Ops diarahkan ke PWA /stock_ops
# (berlaku untuk user tanpa akses Desk; user ber-Desk tetap ke /app).
role_home_page = {
	"Stock Ops User": "stock_ops",
	"Stock Ops Manager": "stock_ops",
}

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "stock_ops.utils.jinja_methods",
# 	"filters": "stock_ops.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "stock_ops.install.before_install"
# after_install = "stock_ops.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "stock_ops.uninstall.before_uninstall"
# after_uninstall = "stock_ops.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "stock_ops.utils.before_app_install"
# after_app_install = "stock_ops.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "stock_ops.utils.before_app_uninstall"
# after_app_uninstall = "stock_ops.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "stock_ops.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "stock_ops.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"stock_ops.tasks.all"
# 	],
# 	"daily": [
# 		"stock_ops.tasks.daily"
# 	],
# 	"hourly": [
# 		"stock_ops.tasks.hourly"
# 	],
# 	"weekly": [
# 		"stock_ops.tasks.weekly"
# 	],
# 	"monthly": [
# 		"stock_ops.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "stock_ops.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "stock_ops.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "stock_ops.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "stock_ops.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["stock_ops.utils.before_request"]
# after_request = ["stock_ops.utils.after_request"]

# Job Events
# ----------
# before_job = ["stock_ops.utils.before_job"]
# after_job = ["stock_ops.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"stock_ops.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# ============================================================
# Stock Ops PWA
# ============================================================

# Buat custom field external_localid + kunci VAPID + role aplikasi saat install
after_install = "stock_ops.setup.install.after_install"

# Self-heal role & izin Stock Ops tiap `bench migrate` (idempoten)
after_migrate = "stock_ops.setup.install.after_migrate"

# Push notification saat dokumen disubmit
doc_events = {
	"Material Request": {"on_submit": "stock_ops.push.notify_doc_submit"},
	"Stock Entry": {"on_submit": "stock_ops.push.notify_doc_submit"},
}

# Custom field ikut ter-export sebagai fixture (reproducible)
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["name", "in", ["Material Request-external_localid", "Stock Entry-external_localid"]]],
	}
]

# PWA disajikan dari folder www/stock_ops/ (index.html + sw.js + manifest.json).
# Tidak perlu website_route_rules: klien pakai hash-routing, dan sub-path (sw.js,
# manifest.json) harus tetap disajikan sebagai file statis (jangan ditangkap route SPA).

