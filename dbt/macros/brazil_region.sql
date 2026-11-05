{#- IBGE macro-regions, the usual grouping for logistics in Brazil. -#}
{% macro brazil_region(state_column) -%}
    case
        when {{ state_column }} in ('AC', 'AM', 'AP', 'PA', 'RO', 'RR', 'TO') then 'Norte'
        when {{ state_column }} in ('AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE') then 'Nordeste'
        when {{ state_column }} in ('DF', 'GO', 'MS', 'MT') then 'Centro-Oeste'
        when {{ state_column }} in ('ES', 'MG', 'RJ', 'SP') then 'Sudeste'
        when {{ state_column }} in ('PR', 'RS', 'SC') then 'Sul'
    end
{%- endmacro %}
