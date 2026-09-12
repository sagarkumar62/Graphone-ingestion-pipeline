from src.sources.base import BaseSourceAdapter
from src.sources.arxiv import ArXivSourceAdapter
from src.sources.news_sources import (
    HuggingFaceDailyPapersSource,
    TechCrunchAISource,
    MITTechReviewAISource,
    OpenAIBlogSource,
    HackerNewsAISource
)
from src.sources.job_sources import (
    RemoteOKAISource,
    ArbeitnowJobSource,
    JobicyAISource,
    HNWhoIsHiringJobSource,
    WeWorkRemotelyAISource,
    AIJobsNetSource,
    YCWorkAtAStartupSource,
    CryptoJobsAISource
)
from src.sources.startup_sources import GitHubOrganizationsStartupSource
from src.sources.product_sources import GitHubRepositoriesProductSource, HuggingFaceModelsProductSource

class SourceRegistry:
    """
    Registry for source adapters.
    Decouples source discovery and extraction strategies from core ingestion pipeline.
    """

    def __init__(self):
        self._registry: dict[str, BaseSourceAdapter] = {}
        self._register_defaults()

    def register(self, name: str, adapter: BaseSourceAdapter) -> None:
        self._registry[name.lower()] = adapter

    def get(self, name: str) -> BaseSourceAdapter | None:
        return self._registry.get(name.lower())

    def list_sources(self) -> list[str]:
        return list(self._registry.keys())

    def _register_defaults(self) -> None:
        arxiv_adapter = ArXivSourceAdapter()
        self.register("arxiv", arxiv_adapter)
        self.register("paperswithcode", arxiv_adapter)

        # Startup Source Adapters
        github_startups = GitHubOrganizationsStartupSource()
        self.register("githuborgs", github_startups)
        self.register("startups", github_startups)

        # Product Source Adapters
        github_products = GitHubRepositoriesProductSource()
        hf_products = HuggingFaceModelsProductSource()
        self.register("githubproducts", github_products)
        self.register("hfmodels", hf_products)
        self.register("products", github_products)

        # 5 AI News Adapters
        self.register("huggingfacedailypapers", HuggingFaceDailyPapersSource())
        self.register("techcrunchai", TechCrunchAISource())
        self.register("mittechreviewai", MITTechReviewAISource())
        self.register("openaiblog", OpenAIBlogSource())
        self.register("hackernewsai", HackerNewsAISource())

        # Job Adapters
        self.register("remoteokai", RemoteOKAISource())
        self.register("arbeitnow", ArbeitnowJobSource())
        self.register("jobicy", JobicyAISource())
        self.register("hnwhoishiring", HNWhoIsHiringJobSource())
        self.register("weworkremotelyai", WeWorkRemotelyAISource())
        self.register("aijobsnet", AIJobsNetSource())
        self.register("ycworkatastartup", YCWorkAtAStartupSource())
        self.register("cryptojobsai", CryptoJobsAISource())
        self.register("jobs", ArbeitnowJobSource())

registry = SourceRegistry()
