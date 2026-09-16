from typing import List, Dict, Tuple
import random
from collections import defaultdict
from .models import QuerySpec, TargetContext

class QueryStrategyEngine:
    def __init__(self, target_ctx: TargetContext, seed_queries: List[str], active_providers: List[str], historical_stats: Dict[str, dict], pregenerated_specs: List[QuerySpec] = None):
        self.target = target_ctx
        self.seed_queries = seed_queries
        self.active_providers = active_providers
        self.history = historical_stats
        self.pregenerated_specs = pregenerated_specs
        self.exploration_ratio = 0.20
        self.min_samples = 3

    def generate_all_rounds(self) -> dict[int, List[QuerySpec]]:
        all_specs = self.pregenerated_specs if self.pregenerated_specs else self._generate_all_combinations()
        
        # Add seeds
        for q in self.seed_queries:
            for p in self.active_providers:
                # Seed queries are treated as priority 999 exploitation
                spec = QuerySpec(text=q, family="SEED_QUERY", round=1, priority=999.0, template=q, provider_name=p, is_exploration=False)
                all_specs.append(spec)
                
        # Split into exploitation vs exploration based on historical performance
        exploitation = []
        exploration = []
        
        # Baseline priority mapping for fallback (P0.7 logic)
        fallback_priority = {
            "COMPANY_DISCOVERY": 80.0,
            "PERSON_DISCOVERY": 60.0,
            "TARGET_PAGE_DISCOVERY": 40.0,
            "GEOGRAPHIC_EXPANSION": 20.0,
            "SEED_QUERY": 999.0
        }
        
        for spec in all_specs:
            if spec.family == "SEED_QUERY":
                exploitation.append(spec)
                continue
                
            key = f"{spec.provider_name}|{spec.family}|{spec.template}"
            if key in self.history:
                stats = self.history[key]
                if stats["query_count"] >= self.min_samples:
                    # Solid history -> Exploitation
                    spec = QuerySpec(
                        text=spec.text,
                        family=spec.family,
                        round=0, 
                        priority=stats["performance_score"],
                        template=spec.template,
                        provider_name=spec.provider_name,
                        is_exploration=False,
                        samples=stats["query_count"]
                    )
                    exploitation.append(spec)
                else:
                    # Needs more samples -> Exploration (but conservatively scored if forced to exploit)
                    spec = QuerySpec(
                        text=spec.text,
                        family=spec.family,
                        round=0,
                        priority=fallback_priority.get(spec.family, 10.0),
                        template=spec.template,
                        provider_name=spec.provider_name,
                        is_exploration=True,
                        samples=stats["query_count"]
                    )
                    exploration.append(spec)
            else:
                # No history at all -> Exploration
                spec = QuerySpec(
                    text=spec.text,
                    family=spec.family,
                    round=0,
                    priority=fallback_priority.get(spec.family, 10.0),
                    template=spec.template,
                    provider_name=spec.provider_name,
                    is_exploration=True
                )
                exploration.append(spec)
                
        # Sort exploitation by priority descending
        exploitation.sort(key=lambda x: x.priority, reverse=True)
        # Sort exploration randomly (or by fallback priority) to vary what we try
        random.shuffle(exploration)
        
        # Build rounds with an 80/20 mix.
        # Say each round gets 5 queries
        QUERIES_PER_ROUND = 5
        MAX_ROUNDS = 4
        
        rounds = defaultdict(list)
        
        exp_idx = 0
        expl_idx = 0
        
        for round_num in range(1, MAX_ROUNDS + 1):
            for _ in range(QUERIES_PER_ROUND):
                # 20% chance for exploration, or if we ran out of exploitation
                if (random.random() < self.exploration_ratio and expl_idx < len(exploration)) or exp_idx >= len(exploitation):
                    if expl_idx < len(exploration):
                        spec = exploration[expl_idx]
                        # Re-assign round for clarity
                        rounds[round_num].append(QuerySpec(
                            text=spec.text, family=spec.family, round=round_num, priority=spec.priority,
                            template=spec.template, provider_name=spec.provider_name, is_exploration=spec.is_exploration, samples=spec.samples
                        ))
                        expl_idx += 1
                elif exp_idx < len(exploitation):
                    spec = exploitation[exp_idx]
                    rounds[round_num].append(QuerySpec(
                        text=spec.text, family=spec.family, round=round_num, priority=spec.priority,
                        template=spec.template, provider_name=spec.provider_name, is_exploration=spec.is_exploration, samples=spec.samples
                    ))
                    exp_idx += 1
                    
        return dict(rounds)

    def _generate_all_combinations(self) -> List[QuerySpec]:
        specs = []
        
        def add_templates(family: str, templates: List[str]):
            for t in templates:
                text = t.replace("{role}", self.target.role)\
                        .replace("{industry}", self.target.industry)\
                        .replace("{location}", self.target.location)\
                        .replace("{country}", self.target.country)
                for provider in self.active_providers:
                    specs.append(QuerySpec(text=text, family=family, round=0, priority=0, template=t, provider_name=provider))

        # COMPANY DISCOVERY
        if self.target.industry and self.target.location:
            add_templates("COMPANY_DISCOVERY", [
                "{industry} companies {location}",
                "{industry} startups {location}",
                "software companies {location}",
                "software startups {location}",
                "technology companies {location}",
                "B2B {industry} {location}",
                "enterprise software {location}"
            ])

        # PERSON DISCOVERY
        if self.target.role and self.target.industry and self.target.location:
            add_templates("PERSON_DISCOVERY", [
                "{role} {industry} {location}",
                '"{role}" {industry} {location}',
                '"{role}" {location}'
            ])

        # TARGET_PAGE_DISCOVERY
        if self.target.industry and self.target.location:
            t_pages = [
                "inurl:team {industry} {location}",
                "inurl:about {industry} {location}",
                "inurl:management {industry} {location}",
                "intitle:team {industry} {location}",
            ]
            if self.target.country.lower() == "switzerland" and self.target.role:
                t_pages.append('site:.ch "{role}" {industry}')
                t_pages.append('site:.ch "{role}" {location}')
            else:
                t_pages.append('inurl:leadership {industry}')
                t_pages.append('inurl:contact {industry}')
            add_templates("TARGET_PAGE_DISCOVERY", t_pages)

        # GEOGRAPHIC EXPANSION
        if self.target.role and self.target.industry and self.target.location:
            variants = []
            if self.target.location.lower() == "zurich":
                variants = [
                    "{role} {industry} Zürich",
                    "{role} {industry} Zurich Switzerland",
                    "{role} {industry} Zürich Schweiz",
                    "{role} {industry} Zürich Suisse",
                    "{role} {industry} CH"
                ]
            else:
                if self.target.country:
                    variants = ["{role} {industry} {location} {country}"]
            add_templates("GEOGRAPHIC_EXPANSION", variants)

        return specs
