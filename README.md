# Folhas de horas semanais

MVP Django para registo de horas por colaborador, semana, cliente e projeto, com revisão pelo responsável de aprovação. A interface está em português de Portugal. As pausas são registadas para informação, mas **não reduzem** o intervalo entre início e fim.

## Funcionalidades

- Administração de clientes e projetos com dados de contacto e aprovador.
- Folhas independentes para cada combinação de colaborador, semana, cliente e projeto.
- Cada projeto define as tarifas por hora normal, extra e de domingo, em euros.
- Registo diário de segunda-feira a domingo; até 8 horas por dia útil são normais, o excedente e todas as horas de sábado são extra. As horas de domingo usam exclusivamente a tarifa de domingo e não acumulam com a tarifa extra.
- A folha apresenta horas e valores por categoria, por dia e no total semanal; os valores são arredondados aos cêntimos por categoria e dia.
- A interface pode ser utilizada em português de Portugal ou inglês. O cabeçalho apresenta apenas o idioma alternativo ao atual: “PT” com a bandeira portuguesa em inglês, ou “GB” com a bandeira britânica em português (também no login e na administração). Cada utilizador autenticado pode escolher o idioma; a preferência fica guardada na conta. Sem preferência, usa-se português de Portugal. A escolha também é memorizada num cookie para utilizadores não autenticados.
- Submissão, aprovação ou devolução com nota e histórico de estados.
- O aprovador acede com uma conta cujo email corresponde ao email configurado no projeto; administradores podem consultar todas as folhas.
- Validação de semana à segunda-feira, relação cliente/projeto, duplicados, horas e pausas.

## Execução local com Docker

Requisitos: Docker Engine e Docker Compose v2. Na pasta do projeto:

```sh
cp .env.example .env
```

Edite `.env`: crie um `SECRET_KEY` único e aleatório, defina palavras-passe fortes e substitua `ALLOWED_HOSTS` pelos nomes DNS/IP efetivos. Para uso apenas local, pode manter `localhost,127.0.0.1`. `POSTGRES_PASSWORD` e `DB_PASSWORD` têm de ser iguais.

```sh
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

Abra `http://localhost:8000/conta/entrar/`. O utilizador de `createsuperuser` administra contas em `/admin/`; crie colaboradores e contas para aprovadores aí. Depois, com a conta de administrador, adicione clientes e projetos na aplicação. O email da conta do aprovador tem de coincidir com o email do responsável configurado no respetivo projeto.

Para parar sem apagar os dados:

```sh
docker compose down
```

Os dados PostgreSQL persistem no volume Docker `postgres_data`; ficheiros estáticos recolhidos são guardados no volume `static_data`. `docker compose down -v` elimina permanentemente os volumes e os dados.

## Deployment numa VM Debian 13

1. Instale Docker Engine e o plugin Docker Compose v2 a partir do repositório oficial da Docker para Debian. Mantenha o sistema e as imagens atualizados e restrinja o acesso SSH e às portas da VM.
2. Copie o repositório para a VM, crie `.env` a partir de `.env.example` e configure uma chave Django aleatória, credenciais exclusivas e fortes para PostgreSQL, `DEBUG=False`, `ALLOWED_HOSTS` com o domínio público e `CSRF_TRUSTED_ORIGINS=https://o-seu-dominio`.
3. Ative `SECURE_SSL_REDIRECT=True` quando o proxy TLS estiver corretamente configurado. Inicie a aplicação com `docker compose up --build -d` e crie o primeiro administrador com `docker compose exec web python manage.py createsuperuser`. As migrações e a recolha de estáticos são executadas no arranque do serviço web.
4. Coloque um proxy inverso como Caddy ou Nginx à frente do serviço web, publique apenas as portas 80/443 e configure o certificado TLS/renovação no proxy. Encaminhe o tráfego para a porta interna 8000 e preserve os cabeçalhos `Host` e `X-Forwarded-Proto: https`. A aplicação confia nesse último cabeçalho para detetar HTTPS.
5. Faça cópias de segurança regulares do volume PostgreSQL (por exemplo, `pg_dump` executado no contentor `db`) e teste a reposição. Proteja o ficheiro `.env`, que contém credenciais, e não o inclua em backups públicos.

Antes de uma atualização, faça backup da base de dados e depois atualize as imagens e execute:

```sh
docker compose build web
docker compose up -d
docker compose exec web python manage.py migrate
```

## Desenvolvimento e testes

Requer Python 3.13 e uma instância PostgreSQL acessível. Instale as dependências em ambiente virtual, configure as variáveis `DB_*` e `SECRET_KEY` e execute:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
python manage.py test
```

Em PowerShell, ative o ambiente virtual com `.venv\Scripts\Activate.ps1`. Os testes podem correr sem um serviço PostgreSQL local através da base SQLite temporária:

```sh
python manage.py test --settings=config.test_settings
```

O serviço da aplicação e o deployment usam sempre PostgreSQL.

### Traduções

O Django fornece as traduções nativas de autenticação e administração para português europeu. As traduções da aplicação em inglês estão em `locale/en/LC_MESSAGES/django.po` e o ficheiro compilado é usado em execução. Ao alterar ou acrescentar texto marcado para tradução, compile o catálogo com GNU gettext instalado:

```sh
python manage.py makemessages -l en
python manage.py compilemessages
```
