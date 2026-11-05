{#- Raw keeps quoted empty strings ("") as ''; staging treats them as missing. -#}
{% macro blank_to_null(column) -%}
    nullif(trim({{ column }}), '')
{%- endmacro %}
