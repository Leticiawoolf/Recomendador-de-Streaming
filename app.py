import streamlit as st
from concurrent.futures import ThreadPoolExecutor
from simplejustwatchapi.justwatch import search
import re

st.set_page_config(page_title="Recomendador Universal de Streaming", page_icon="🎬", layout="wide")

# CSS personalizado para design premium e melhor UX mobile/desktop
st.markdown("""
<style>
    .movie-card {
        background-color: white;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border: 1px solid #e9ecef;
    }
    .movie-title {
        font-size: 24px;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 8px;
    }
    .badges {
        margin-bottom: 12px;
    }
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 16px;
        font-size: 13px;
        font-weight: 600;
        margin-right: 8px;
        margin-bottom: 8px;
    }
    .badge.score { background-color: #fff3cd; color: #856404; }
    .badge.provider { background-color: #e9ecef; color: #495057; }
    .badge.year { background-color: #e3f2fd; color: #0d47a1; }
    .movie-synopsis {
        font-size: 15px;
        line-height: 1.6;
        color: #4a5568;
    }
    .imdb-link a {
        text-decoration: none;
        color: #007bff;
        font-weight: 600;
    }
    .imdb-link a:hover {
        text-decoration: underline;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎬 Recomendador Universal de Streaming")
st.markdown("Descubra o que assistir hoje nos seus catálogos de streaming.")

# --- BARRA LATERAL PARA FILTROS ---
with st.sidebar:
    st.header("⚙️ Filtros")
    
    st.subheader("Serviços de Streaming")
    col1, col2 = st.columns(2)
    with col1:
        nfx = st.checkbox("Netflix", value=True)
        gop = st.checkbox("Globoplay", value=True)
        dnp = st.checkbox("Disney+", value=True)
    with col2:
        prv = st.checkbox("Prime Video", value=True)
        mxx = st.checkbox("Max", value=True)
        
    providers_cb = {
        "Netflix": nfx,
        "Amazon Video": prv,
        "Globoplay": gop,
        "Max": mxx,
        "Disney Plus": dnp
    }
    
    st.divider()
    st.subheader("Catálogo e Gênero")
    fmt = st.selectbox("Formato", ["Qualquer", "Filme", "Série"])
    gnr = st.selectbox("Gênero Principal", ["Qualquer", "Comédia", "Drama", "Ação", "Documentário", "Ficção Científica", "Romance", "Terror", "Animação"])
    
    st.divider()
    st.subheader("Características")
    if fmt == "Série":
        max_eps = st.slider("Número máximo de episódios", 1, 500, 100, step=10)
        rt = None
    else:
        rt = st.slider("Duração máxima (minutos)", 30, 180, 120, step=15)
        max_eps = None
    rt_min = st.slider("Nota Mínima (IMDb)", 0.0, 10.0, 0.0, step=0.5)
    
    st.divider()
    st.subheader("Elenco (Buscar Específico)")
    cast = st.text_input("Nome do Ator/Atriz", placeholder="Ex: Wagner Moura")
    hide_anim = st.checkbox("Ocultar Trabalhos de Dublagem", value=True)
    
    search_btn = st.button("Buscar Recomendações", use_container_width=True, type="primary")

# --- LÓGICA MAIN ---
if search_btn:
    # Captura os provedores selecionados (case insensitive array)
    selected_providers = [p.lower() for p, v in providers_cb.items() if v]
    
    if not selected_providers:
        st.error("Por favor, selecione pelo menos um serviço de streaming!")
        st.stop()

    with st.spinner("Buscando e filtrando no catálogo JustWatch..."):
        jw_genres_map = {
            "Comédia": "cmy", "Drama": "drm", "Ação": "act", 
            "Documentário": "doc", "Ficção Científica": "scf", 
            "Romance": "rma", "Terror": "hrr", "Animação": "ani"
        }
        
        provider_slugs = {
            "Netflix": "nfx", "Amazon Video": "prv", 
            "Globoplay": "gop", "Max": "mxx", "Disney Plus": "dnp"
        }
        
        # Array oficial pro API JustWatch
        selected_provider_ids = [provider_slugs[p] for p, v in providers_cb.items() if v]
        
        cast_name = cast.strip()
        query_terms = []
        if cast_name:
            query_terms.append(cast_name)
        
        query_string = " ".join(query_terms)
        
        filtered_results = []
        seen_ids = set()
        
        def apply_filters(batch):
            cast_radicals = [p.lower()[:4] for p in cast_name.split() if len(p) > 3] if cast_name else []
            local_results = []
            
            for item in batch:
                if getattr(item, 'object_id', None) in seen_ids:
                    continue
                    
                title_lower = getattr(item, 'title', '').lower()
                overview_lower = getattr(item, 'short_description', '').lower()
                text_to_check = title_lower + " " + overview_lower
                
                # Heurística Anti-Alucinação para atores
                is_hallucination = False
                if cast_name:
                    for rad in cast_radicals:
                        if re.search(rf'\b{rad}', text_to_check):
                            if cast_name.lower() not in text_to_check:
                                is_hallucination = True
                                break
                
                if is_hallucination:
                    continue
                    
                item_genres = getattr(item, 'genres', [])
                
                if gnr != "Qualquer":
                    target_gnr = jw_genres_map.get(gnr)
                    if target_gnr and target_gnr not in item_genres:
                        continue
                        
                if hide_anim and gnr != "Animação" and "ani" in item_genres:
                    continue
                        
                if fmt == "Filme" and getattr(item, 'object_type', '') != 'MOVIE':
                    continue
                if fmt == "Série" and getattr(item, 'object_type', '') != 'SHOW':
                    continue
                    
                if rt is not None:
                    runtime = getattr(item, 'runtime_minutes', 0)
                    if runtime and runtime > rt:
                        continue
                if max_eps is not None and getattr(item, 'object_type', '') == 'SHOW':
                    episodes = getattr(item, 'total_episode_count', 0)
                    if episodes and episodes > max_eps:
                        continue
                
                score = 0
                if hasattr(item, 'scoring') and item.scoring:
                    # Tenta IMDb ou TMDB
                    score = getattr(item.scoring, 'imdb_score', 0) or getattr(item.scoring, 'tmdb_score', 0) or 0
                if score < rt_min:
                    continue
                
                # Confirmando a presença para assinatura Plana (FLATRATE)
                providers_found = []
                if hasattr(item, 'offers') and item.offers:
                    for offer in item.offers:
                        if offer.monetization_type == 'FLATRATE' and offer.package:
                            p_name = offer.package.name.lower()
                            for sp in selected_providers:
                                if sp in p_name:
                                    providers_found.append(offer.package.name)
                
                if providers_found:
                    seen_ids.add(getattr(item, 'object_id'))
                    local_results.append((item, list(set(providers_found))))
            return local_results

        if cast_name:
            results = search(query_string, "BR", "pt-BR", 25, offset=0)
            if results:
                filtered_results.extend(apply_filters(results))
        else:
            def fetch_chunk(off):
                try:
                    return search(query_string, "BR", "pt-BR", 100, offset=off, providers=selected_provider_ids)
                except Exception:
                    return []
                    
            with ThreadPoolExecutor(max_workers=10) as executor:
                offsets_to_fetch = range(0, 2000, 100)
                for results_batch in executor.map(fetch_chunk, offsets_to_fetch):
                    if results_batch:
                        filtered_results.extend(apply_filters(results_batch))
                        
    # Fim do Spinner, mostrar resultados
    if not filtered_results:
        if cast_name:
            st.error("Não existem títulos desse ator atrelados aos filtros escolhidos.")
        else:
            st.warning("Nenhuma recomendação atendeu a esse conjunto de filtros. Tente marcar mais serviços de streaming ou mudar o formato.")
    else:
        def get_score(item_tuple):
            item = item_tuple[0]
            if hasattr(item, 'scoring') and item.scoring:
                return getattr(item.scoring, 'imdb_score', 0) or getattr(item.scoring, 'tmdb_score', 0) or 0
            return 0
            
        filtered_results.sort(key=get_score, reverse=True)
        top_5 = filtered_results[:5]
        
        st.subheader(f"🏆 Suas Top {len(top_5)} Recomendações:")
        
        for i, (choice, providers_list) in enumerate(top_5, 1):
            year = getattr(choice, 'release_year', None)
            score = get_score((choice, providers_list))
            score_str = f"⭐ {score:.1f}/10" if score > 0 else "⭐ N/A"
            overview = getattr(choice, 'short_description', "Sinopse não disponível.")
            overview = overview.replace('\n', ' ').strip()
            
            provider_badges = "".join([f'<span class="badge provider">{p}</span>' for p in providers_list])
            year_badge = f'<span class="badge year">{year}</span>' if year else ''
            
            imdb_link = ""
            if getattr(choice, 'imdb_id', None):
                imdb_link = f"<div class='imdb-link'><a href='https://www.imdb.com/title/{choice.imdb_id}/' target='_blank'>🔗 Abrir no IMDb</a></div>"
                
            st.markdown(f"""
            <div class="movie-card">
                <div class="movie-title">{i}. {choice.title}</div>
                <div class="badges">
                    <span class="badge score">{score_str}</span>
                    {year_badge}
                    {provider_badges}
                </div>
                <div class="movie-synopsis">{overview}</div>
                {imdb_link}
            </div>
            """, unsafe_allow_html=True)
