from core.models import SiteConfig


def site_context(request):
    config = SiteConfig.load()
    return {
        'site_title': config.site_title,
        'site_tagline': config.tagline,
    }
