---
layout: page
title: League rules
permalink: /rules/
description: The league's rules and how its standings are worked out.
---
{% include core/context.html %}

<div class="st-page-title" markdown="1">
# League rules
{: .st-page-title__title}
</div>

<div class="st-section__head" markdown="1">
## The rules
{: .st-section__title}
</div>

[League rules] The league has not written its rules down yet. Whoever sets up the site writes them here, in the file `rules/index.md`: how many players a team needs, how fouls are called, what happens when a game is late.

<div class="st-section__head" markdown="1">
## How the standings work
{: .st-section__title}
</div>

{{ stats.standings.note }}
{: .st-note}

{{ stats.standings.tiebreak_note }}
{: .st-note}

{% if league.placeholders.size > 0 %}
<div class="st-section__head" markdown="1">
## Still to decide
{: .st-section__title}
</div>

These settings have no answer yet. The site shows `[placeholder]` wherever they come up. They are set in `league.yml`.

{% for item in league.placeholders -%}
- {{ item.text }} (`{{ item.setting }}`)
{% endfor %}
{: .st-note}
{% endif %}
