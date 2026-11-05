{#- The warehouse layers are fixed schemas (raw, staging, intermediate, marts), so the custom
    schema is used as-is instead of dbt's default "<target>_<custom>" prefix. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
