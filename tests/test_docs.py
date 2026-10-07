from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path
import pytest, yaml
sys.path.insert(0,str(Path(__file__).parents[1]/"scripts"))
import collect_docs
from collect_docs import (
    MARKDOWN_POLICY_EXTENSIONS,
    CollectionError,
    assemble,
    load_manifest,
)
from validate_docs import validate
from update_source_locks import main as update_source_locks_main
from update_source_locks import update as update_source_locks

def git(repo:Path,*args:str)->str:return subprocess.run(["git",*args],cwd=repo,check=True,capture_output=True,text=True).stdout.strip()
def repo(root:Path,name:str,text:str)->tuple[Path,str]:
 r=root/name;r.mkdir();git(r,"init","-q");git(r,"config","user.email","t@invalid");git(r,"config","user.name","T");(r/"README.md").write_text(text);(r/"LICENSE").write_text("MIT License\n");git(r,"add",".");git(r,"commit","-qm","content");content=git(r,"rev-parse","HEAD")
 rights={"spdx_license":"MIT","license_file":"LICENSE"};
 if name=="dasc":rights["attribution"]="Test"
 contract={"schema_version":1,"project":name,"repository":f"https://github.com/pydasc/{name}","source_commit":content,"files":[{"source":"README.md","destination":f"{name}/index.md","media_type":"text/markdown","documentation_status":{"label":"Reviewed","evidence":"test"},"redistribution":rights}]}
 if name=="dasc":contract["publication_decision"]={"state":"approved","reason":"test","evidence":"test"}
 (r/"docs").mkdir();(r/"docs/publication-manifest.json").write_text(json.dumps(contract));git(r,"add",".");git(r,"commit","-qm","contract");return r,git(r,"rev-parse","HEAD")
def fixture(tmp:Path,ptext="# P\n",dtext="# D\n"):
 p,pc=repo(tmp,"pydasc",ptext);d,dc=repo(tmp,"dasc",dtext);data={"schema_version":2,"sources":{n:{"repository":f"https://github.com/pydasc/{n}","checkout_commit":c,"publication_manifest":"docs/publication-manifest.json","files":[{"source":"README.md","destination":f"{n}/index.md"}]} for n,c in (("pydasc",pc),("dasc",dc))}};m=tmp/"lock.yml";m.write_text(yaml.safe_dump(data));return m,p,d
def hashes(root:Path):return {x.relative_to(root):hashlib.sha256(x.read_bytes()).hexdigest() for x in root.rglob("*") if x.is_file() and ".git" not in x.parts}
def test_deterministic_inventory_validation_and_source_immutability(tmp_path):
 m,p,d=fixture(tmp_path);before=(hashes(p),hashes(d));out=tmp_path/"out";first=assemble(m,out,p,d);validate(m,out);second=assemble(m,out,p,d);assert first==second;assert before==(hashes(p),hashes(d));assert len(first)==2
 generated=(out/"pydasc/index.md").read_text()
 assert '!!! info "Publication record"' in generated
 assert "**Project:** PyDASC" in generated
 assert first[1]["commit"] in generated
def test_commit_mismatch_rejected(tmp_path):
 m,p,d=fixture(tmp_path);data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]="a"*40;m.write_text(yaml.safe_dump(data));
 with pytest.raises(CollectionError,match="commit mismatch"):assemble(m,tmp_path/"out",p,d)

def test_dirty_publication_manifest_rejected(tmp_path):
 m,p,d=fixture(tmp_path);contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["files"][0]["documentation_status"]["evidence"]="uncommitted approval";contract_path.write_text(json.dumps(contract))
 with pytest.raises(CollectionError,match="differs from locked commit"):assemble(m,tmp_path/"out",p,d)

def test_transferred_repository_identity_is_accepted_from_exact_alias(tmp_path):
 m,p,d=fixture(tmp_path);contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["repository"]="https://github.com/chongshikpark/pydasc";contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","pre-transfer contract");commit=git(p,"rev-parse","HEAD");data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=commit;m.write_text(yaml.safe_dump(data))
 assemble(m,tmp_path/"accepted",p,d)

def test_unrecognized_repository_identity_is_rejected(tmp_path):
 m,p,d=fixture(tmp_path);contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["repository"]="https://github.com/example/pydasc";contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","unrecognized repository");data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD");m.write_text(yaml.safe_dump(data))
 with pytest.raises(CollectionError,match="publication identity"):assemble(m,tmp_path/"rejected",p,d)

@pytest.mark.parametrize("collision", ["source", "destination"])
def test_duplicate_upstream_contract_paths_rejected_case_insensitively(tmp_path, collision):
 m,p,d=fixture(tmp_path);contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());duplicate=json.loads(json.dumps(contract["files"][0]))
 if collision=="source":duplicate["source"]="readme.MD";duplicate["destination"]="pydasc/other.md"
 else:duplicate["source"]="OTHER.md";duplicate["destination"]="pydasc/INDEX.md"
 contract["files"].append(duplicate);contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","duplicate contract path");data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD");m.write_text(yaml.safe_dump(data))
 with pytest.raises(CollectionError,match=f"duplicate approved {collision}"):assemble(m,tmp_path/"out",p,d)

def test_source_lock_update_validates_candidate_and_changes_only_commit(tmp_path):
 m,p,d=fixture(tmp_path);before=yaml.safe_load(m.read_text());(p/"CHANGELOG.md").write_text("candidate\n");git(p,"add","CHANGELOG.md");git(p,"commit","-qm","candidate")
 changes=update_source_locks(m,{"pydasc":p,"dasc":d});after=yaml.safe_load(m.read_text())
 assert changes=={"pydasc":(before["sources"]["pydasc"]["checkout_commit"],git(p,"rev-parse","HEAD"))}
 assert after["sources"]["pydasc"]["checkout_commit"]==git(p,"rev-parse","HEAD")
 before["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD")
 assert after==before

def test_source_lock_update_accepts_transferred_repository_contract_alias(tmp_path):
 m,p,d=fixture(tmp_path);contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["repository"]="https://github.com/chongshikpark/pydasc";contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","transferred repository contract")
 previous=yaml.safe_load(m.read_text())["sources"]["pydasc"]["checkout_commit"]
 changes=update_source_locks(m,{"pydasc":p,"dasc":d})
 assert changes=={"pydasc":(previous,git(p,"rev-parse","HEAD"))}

def test_source_lock_cli_skips_unapproved_candidate_without_changes(tmp_path,capsys):
 m,p,d=fixture(tmp_path);before=m.read_bytes();contract_path=d/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["publication_decision"]["state"]="draft";contract_path.write_text(json.dumps(contract));git(d,"add",str(contract_path.relative_to(d)));git(d,"commit","-qm","draft contract")
 rejected=update_source_locks_main(["--manifest",str(m),"--pydasc",str(p),"--dasc",str(d)])
 assert rejected==1;assert m.read_bytes()==before;assert "error: DASC publication decision is not approved" in capsys.readouterr().err
 result=update_source_locks_main(["--skip-unapproved","--manifest",str(m),"--pydasc",str(p),"--dasc",str(d)])
 assert result==0;assert m.read_bytes()==before;assert "skip: DASC publication decision is not approved" in capsys.readouterr().out

@pytest.mark.parametrize(("section", "field", "value", "pattern"), [
 ("decision", "reason", "", "decision evidence"),
 ("decision", "evidence", 7, "decision evidence"),
 ("attribution", "attribution", "", "attribution"),
 ("attribution", "attribution", ["invalid"], "attribution"),
 ("attribution", "attribution", "<b>unsafe</b>", "attribution"),
 ("attribution", "attribution", "invalid--comment", "attribution"),
])
def test_dasc_decision_evidence_and_attribution_must_be_nonempty_strings(tmp_path, section, field, value, pattern):
 m,p,d=fixture(tmp_path);contract_path=d/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text())
 if section=="decision":contract["publication_decision"][field]=value
 else:contract["files"][0]["redistribution"][field]=value
 contract_path.write_text(json.dumps(contract));git(d,"add","docs/publication-manifest.json");git(d,"commit","-qm","invalid publication metadata");data=yaml.safe_load(m.read_text());data["sources"]["dasc"]["checkout_commit"]=git(d,"rev-parse","HEAD");m.write_text(yaml.safe_dump(data))
 with pytest.raises(CollectionError,match=pattern):assemble(m,tmp_path/"out",p,d)
@pytest.mark.parametrize("value",["/README.md","../README.md","*.md","secret.env"])
def test_unsafe_selection_rejected(tmp_path,value):
 m,p,d=fixture(tmp_path);data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["files"][0]["source"]=value;m.write_text(yaml.safe_dump(data));
 with pytest.raises(CollectionError):assemble(m,tmp_path/"out",p,d)

@pytest.mark.parametrize("value", ["bad\nname.md", "bad\tname.md", "bad`name.md", "bad\x7fname.md"])
def test_manifest_paths_reject_controls_and_markdown_delimiters(tmp_path,value):
 m,p,d=fixture(tmp_path);data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["files"][0]["destination"]=f"pydasc/{value}";m.write_text(yaml.safe_dump(data))
 with pytest.raises(CollectionError,match="POSIX path"):load_manifest(m)
def test_unapproved_and_casefold_collision_rejected(tmp_path):
 m,p,d=fixture(tmp_path);data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["files"].append({"source":"README.md","destination":"pydasc/INDEX.md"});m.write_text(yaml.safe_dump(data));
 with pytest.raises(CollectionError,match="duplicate"):assemble(m,tmp_path/"out",p,d)
def test_broken_link_and_credential_rejected(tmp_path):
 for text,pattern in (("[bad](missing.md)\n","broken"),("github_pat_secret\n","credential")):
  root=tmp_path/pattern;root.mkdir();m,p,d=fixture(root,ptext=text)
  with pytest.raises(CollectionError,match=pattern):assemble(m,root/"out",p,d)

def test_relative_links_relocate_or_use_exact_immutable_source_revision(tmp_path):
 m,p,d=fixture(tmp_path);(p/"README.md").write_text("# P\n\n[Guide](guide.md?view=full#intro)\n[Notes](notes.md?raw=1#top)\n");(p/"guide.md").write_text("# Guide\n");(p/"notes.md").write_text("# Notes\n");git(p,"add","README.md","guide.md","notes.md");git(p,"commit","-qm","linked content");content=git(p,"rev-parse","HEAD")
 contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["source_commit"]=content;contract["files"].append({"source":"guide.md","destination":"pydasc/guides/guide.md","media_type":"text/markdown","documentation_status":{"label":"Reviewed","evidence":"test"},"redistribution":{"spdx_license":"MIT","license_file":"LICENSE"}});contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","approve linked content")
 data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD");data["sources"]["pydasc"]["files"].append({"source":"guide.md","destination":"pydasc/guides/guide.md"});m.write_text(yaml.safe_dump(data));out=tmp_path/"out";assemble(m,out,p,d);generated=(out/"pydasc/index.md").read_text()
 assert "[Guide](guides/guide.md?view=full#intro)" in generated
 assert f"[Notes](https://github.com/pydasc/pydasc/blob/{content}/notes.md?raw=1#top)" in generated

def test_rewritten_links_url_encode_decoded_path_characters(tmp_path):
 m,p,d=fixture(tmp_path);(p/"README.md").write_text("# P\n\n[Selected](selected%20%28한글%29%23.md#section)\n[Other](other%20%28한글%29%23%3F.md?raw=1#top)\n");selected=p/"selected (한글)#.md";other=p/"other (한글)#?.md";selected.write_text("# Selected\n");other.write_text("# Other\n");git(p,"add","README.md",selected.name,other.name);git(p,"commit","-qm","encoded link targets");content=git(p,"rev-parse","HEAD")
 contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["source_commit"]=content;contract["files"].append({"source":selected.name,"destination":"pydasc/guides/selected (한글)#.md","media_type":"text/markdown","documentation_status":{"label":"Reviewed","evidence":"test"},"redistribution":{"spdx_license":"MIT","license_file":"LICENSE"}});contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","approve encoded link target")
 data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD");data["sources"]["pydasc"]["files"].append({"source":selected.name,"destination":"pydasc/guides/selected (한글)#.md"});m.write_text(yaml.safe_dump(data));out=tmp_path/"out";assemble(m,out,p,d);generated=(out/"pydasc/index.md").read_text()
 assert "[Selected](guides/selected%20%28%ED%95%9C%EA%B8%80%29%23.md#section)" in generated
 assert f"[Other](https://github.com/pydasc/pydasc/blob/{content}/other%20%28%ED%95%9C%EA%B8%80%29%23%3F.md?raw=1#top)" in generated
 selected_page=(out/"pydasc/guides/selected (한글)#.md").read_text();encoded_source="selected%20%28%ED%95%9C%EA%B8%80%29%23.md";source_url=f"https://github.com/pydasc/pydasc/blob/{content}/{encoded_source}"
 assert f"source={source_url};" in selected_page
 assert f"]({source_url})" in selected_page
 validate(m,out)

def test_query_only_link_retains_current_page_semantics(tmp_path):
 m,p,d=fixture(tmp_path,ptext="# P\n\n[View](?plain=1#details)\n");out=tmp_path/"out";assemble(m,out,p,d)
 assert "[View](?plain=1#details)" in (out/"pydasc/index.md").read_text()
 validate(m,out)

def test_empty_link_retains_current_page_semantics(tmp_path):
 m,p,d=fixture(tmp_path,ptext="# P\n\n[Current page]()\n");out=tmp_path/"out";assemble(m,out,p,d)
 assert "[Current page]()" in (out/"pydasc/index.md").read_text()
 validate(m,out)

@pytest.mark.parametrize("target", ["bad%00.md", "bad%0A.md", "bad%7F.md", "bad%5Cname.md", "bad%FF.md", "bad%ZZ.md", "bad%.md"])
def test_encoded_unsafe_or_invalid_link_paths_fail_cleanly(tmp_path,target):
 m,p,d=fixture(tmp_path,ptext=f"# P\n\n[Bad]({target})\n")
 with pytest.raises(CollectionError,match="link path"):assemble(m,tmp_path/"out",p,d)

@pytest.mark.parametrize("target", ["//[invalid", "https://[invalid", "//example.com:bad]"])
def test_malformed_link_authorities_fail_cleanly(tmp_path,target):
 m,p,d=fixture(tmp_path,ptext=f"# P\n\n[Bad]({target})\n")
 with pytest.raises(CollectionError,match="invalid link URL"):assemble(m,tmp_path/"out",p,d)

def test_link_like_text_in_code_or_escapes_is_not_rewritten(tmp_path):
 text="# P\n\n`[inline](missing.md)`\n\n``[long inline](missing.md)``\n\n```text\n```not a closing fence\n[fenced](missing.md)\n```\n\n    [indented](missing.md)\n\n\\[escaped](missing.md)\n"
 m,p,d=fixture(tmp_path,ptext=text);out=tmp_path/"out";assemble(m,out,p,d);generated=(out/"pydasc/index.md").read_text()
 for sample in ("[inline](missing.md)", "[long inline](missing.md)", "[fenced](missing.md)", "[indented](missing.md)", r"\[escaped](missing.md)"):
  assert sample in generated
 validate(m,out)

@pytest.mark.parametrize("target", ["<guide file.md>", "<guide.md>"])
def test_angle_bracket_link_destinations_are_rejected(tmp_path,target):
 m,p,d=fixture(tmp_path,ptext=f"# P\n\n[Guide]({target})\n")
 with pytest.raises(CollectionError,match="angle-bracket link destinations"):assemble(m,tmp_path/"out",p,d)

def test_nested_labels_and_balanced_destination_parentheses_are_rewritten(tmp_path):
 m,p,d=fixture(tmp_path);(p/"README.md").write_text("# P\n\n[Nested [label]](guide(section).md \"Guide title\")\n");(p/"guide(section).md").write_text("# Guide\n");git(p,"add","README.md","guide(section).md");git(p,"commit","-qm","balanced link syntax");content=git(p,"rev-parse","HEAD");contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["source_commit"]=content;contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","approve balanced link revision");data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD");m.write_text(yaml.safe_dump(data));out=tmp_path/"out";assemble(m,out,p,d);generated=(out/"pydasc/index.md").read_text()
 assert f'[Nested [label]](https://github.com/pydasc/pydasc/blob/{content}/guide%28section%29.md "Guide title")' in generated

def test_reference_definition_inside_code_is_ignored(tmp_path):
 text="# P\n\n```markdown\n[guide]: missing.md\n```\n\n    [other]: missing.md\n\n\t[tabbed]: missing.md\n"
 m,p,d=fixture(tmp_path,ptext=text);out=tmp_path/"out";assemble(m,out,p,d);validate(m,out)

@pytest.mark.parametrize("fence", ["```", "~~~"])
@pytest.mark.parametrize("prefix", ["> ", "> > "])
def test_reference_definition_inside_nested_superfence_is_ignored(tmp_path,fence,prefix):
 text=f"# P\n\n{prefix}{fence}markdown\n{prefix}[guide]: missing.md\n{prefix}[example](missing.md)\n{prefix}![image](missing.png)\n{prefix}{fence}\n{prefix.rstrip()}\n{prefix}[Guide][guide]\n"
 m,p,d=fixture(tmp_path,ptext=text);out=tmp_path/"out";assemble(m,out,p,d);validate(m,out)

@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_list_fence_like_syntax_follows_configured_renderer(tmp_path,fence):
 text=f"# P\n\n- {fence}markdown\n  [example](missing.md)\n  ![image](missing.png)\n  {fence}\n"
 m,p,d=fixture(tmp_path,ptext=text)
 if fence == "```":
  out=tmp_path/"out";assemble(m,out,p,d);validate(m,out)
 else:
  with pytest.raises(CollectionError,match="broken or unsafe relative link"):assemble(m,tmp_path/"out",p,d)

def test_renderer_prevents_false_fence_mask_from_hiding_active_link(tmp_path):
 text="# P\n\n> - ~~~markdown\n>   [active](missing.md)\n>   ~~~\n"
 m,p,d=fixture(tmp_path,ptext=text)
 with pytest.raises(CollectionError,match="broken or unsafe relative link"):assemble(m,tmp_path/"out",p,d)

@pytest.mark.parametrize("definition", ["> [guide]: missing.md", "- [guide]: missing.md", "> - [guide]: missing.md", "1. > [guide]: missing.md", "-\t[guide]: missing.md", ">\t[guide]: missing.md", ">\t-\t[guide]: missing.md", "> \t[guide]: missing.md", ">  \t[guide]: missing.md"])
def test_reference_definitions_inside_containers_are_rejected(tmp_path,definition):
 m,p,d=fixture(tmp_path,ptext=f"# P\n\n{definition}\n\n[Guide][guide]\n")
 with pytest.raises(CollectionError,match="reference-style links are not allowed"):assemble(m,tmp_path/"out",p,d)

def test_unlisted_link_target_must_exist_at_exact_content_commit(tmp_path):
 m,p,d=fixture(tmp_path);(p/"README.md").write_text("# P\n\n[Future](future.md)\n");git(p,"add","README.md");git(p,"commit","-qm","link before target");content=git(p,"rev-parse","HEAD");(p/"future.md").write_text("# Future\n");contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["source_commit"]=content;contract_path.write_text(json.dumps(contract));git(p,"add","future.md","docs/publication-manifest.json");git(p,"commit","-qm","add target later")
 data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD");m.write_text(yaml.safe_dump(data))
 with pytest.raises(CollectionError,match="broken or unsafe relative link"):assemble(m,tmp_path/"out",p,d)

def test_unlisted_link_target_cannot_be_a_git_symlink(tmp_path):
 m,p,d=fixture(tmp_path);(p/"README.md").write_text("# P\n\n[Alias](alias.md)\n");(p/"target.md").write_text("# Target\n");(p/"alias.md").symlink_to("target.md");git(p,"add","README.md","target.md","alias.md");git(p,"commit","-qm","symlink target");content=git(p,"rev-parse","HEAD");contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["source_commit"]=content;contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","approve symlink source revision")
 data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD");m.write_text(yaml.safe_dump(data))
 with pytest.raises(CollectionError,match="broken or unsafe relative link"):assemble(m,tmp_path/"out",p,d)

@pytest.mark.parametrize("html", [
 "<script>alert(1)</script>",
 '<iframe src="https://example.invalid"></iframe>',
 '<object data="payload"></object>',
 '<embed src="payload">',
 '<p onclick="alert(1)">active</p>',
 '<a href="javascript:alert(1)">active</a>',
 '<a\n href="javascript:alert(1)">active</a>',
 '<div style="background-image:url(https://example.invalid/track)"></div>',
 '<img srcset="https://example.invalid/track 1x">',
 '<q\n cite="https://example.invalid/track">active</q>',
])
def test_raw_html_is_rejected_from_imported_markdown(tmp_path, html):
 m,p,d=fixture(tmp_path,ptext=f"# P\n\n{html}\n")
 with pytest.raises(CollectionError,match="active raw HTML is not allowed"):assemble(m,tmp_path/"out",p,d)

def test_raw_html_examples_inside_code_are_inert(tmp_path):
 text="# P\n\n`<img src=tracker.png>`\n\n```html\n<script>alert(1)</script>\n```\n\n    <iframe src=tracker.html></iframe>\n"
 m,p,d=fixture(tmp_path,ptext=text);out=tmp_path/"out";assemble(m,out,p,d);validate(m,out)

def test_license_must_be_a_regular_git_blob(tmp_path):
 m,p,d=fixture(tmp_path);license_path=p/"LICENSE";license_path.unlink();license_path.symlink_to("README.md");git(p,"add","LICENSE");git(p,"commit","-qm","symlink license");content=git(p,"rev-parse","HEAD");contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["source_commit"]=content;contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","contract with symlink license");data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD");m.write_text(yaml.safe_dump(data))
 with pytest.raises(CollectionError,match="unsafe license"):assemble(m,tmp_path/"out",p,d)

@pytest.mark.parametrize("definition", ["[guide]: other.md", "[logo]: image.png"])
def test_reference_style_links_are_rejected(tmp_path, definition):
 m,p,d=fixture(tmp_path,ptext=f"# P\n\n{definition}\n")
 with pytest.raises(CollectionError,match="reference-style links are not allowed"):assemble(m,tmp_path/"out",p,d)

def test_markdown_autolink_is_not_mistaken_for_raw_html(tmp_path):
 m,p,d=fixture(tmp_path,ptext="# P\n\n<https://example.com/>\n");out=tmp_path/"out";assemble(m,out,p,d)
 assert "<https://example.com/>" in (out/"pydasc/index.md").read_text()

def test_inert_angle_bracket_placeholder_is_not_mistaken_for_active_html(tmp_path):
 m,p,d=fixture(tmp_path,ptext="# P\n\nrevision: <git-sha>\n");out=tmp_path/"out";assemble(m,out,p,d)
 assert "<git-sha>" in (out/"pydasc/index.md").read_text()
def test_unknown_output_and_checksum_rejected(tmp_path):
 m,p,d=fixture(tmp_path);out=tmp_path/"out";assemble(m,out,p,d);(out/"dasc/extra.md").write_text("x")
 with pytest.raises(CollectionError,match="boundary"):validate(m,out)

@pytest.mark.parametrize("destination", ["/pydasc/index.md", "../index.md", "pydasc/../index.md", "dasc/index.md"])
def test_unsafe_destination_rejected(tmp_path, destination):
 m,p,d=fixture(tmp_path);data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["files"][0]["destination"]=destination;m.write_text(yaml.safe_dump(data))
 with pytest.raises(CollectionError):assemble(m,tmp_path/"out",p,d)

@pytest.mark.parametrize("mutation", ["schema", "root_key", "source_key", "repository", "short_commit"])
def test_manifest_schema_identity_and_unknown_keys_rejected(tmp_path, mutation):
 m,p,d=fixture(tmp_path);data=yaml.safe_load(m.read_text())
 if mutation=="schema":data["schema_version"]=999
 elif mutation=="root_key":data["unexpected"]=True
 elif mutation=="source_key":data["sources"]["pydasc"]["unexpected"]=True
 elif mutation=="repository":data["sources"]["pydasc"]["repository"]="https://github.com/example/pydasc"
 else:data["sources"]["pydasc"]["checkout_commit"]="abc123"
 m.write_text(yaml.safe_dump(data))
 with pytest.raises(CollectionError):load_manifest(m)

def test_source_symlink_and_non_regular_file_rejected(tmp_path):
 for kind in ("symlink", "directory"):
  root=tmp_path/kind;root.mkdir();m,p,d=fixture(root);source=p/"README.md";source.unlink()
  if kind=="symlink":
   outside=root/"outside.md";outside.write_text("outside\n");source.symlink_to(outside)
  else:source.mkdir()
  with pytest.raises(CollectionError,match="unsafe or missing source"):assemble(m,root/"out",p,d)

def test_oversized_source_rejected(tmp_path, monkeypatch):
 m,p,d=fixture(tmp_path,ptext="# P\n" + "x" * 2048);monkeypatch.setattr(collect_docs,"MAX_FILE_BYTES",1024)
 with pytest.raises(CollectionError,match="oversized source"):assemble(m,tmp_path/"out",p,d)

def test_approved_but_missing_source_is_rejected(tmp_path):
 m,p,d=fixture(tmp_path);contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["files"].append({"source":"missing.md","destination":"pydasc/missing.md","media_type":"text/markdown","documentation_status":{"label":"Reviewed","evidence":"test"},"redistribution":{"spdx_license":"MIT","license_file":"LICENSE"}});contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","approve missing file")
 data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD");data["sources"]["pydasc"]["files"].append({"source":"missing.md","destination":"pydasc/missing.md"});m.write_text(yaml.safe_dump(data))
 with pytest.raises(CollectionError,match="unsafe or missing source"):assemble(m,tmp_path/"out",p,d)

def test_stale_generated_file_is_removed_only_inside_namespace(tmp_path):
 m,p,d=fixture(tmp_path);out=tmp_path/"out";assemble(m,out,p,d);stale=out/"pydasc/stale.md";stale.write_text("stale\n");portal=out/"portal.md";portal.write_text("keep\n");assemble(m,out,p,d)
 assert not stale.exists();assert portal.read_text()=="keep\n"

def test_unapproved_image_is_rejected(tmp_path):
 m,p,d=fixture(tmp_path,ptext="# P\n\n![License](LICENSE)\n")
 with pytest.raises(CollectionError,match="image is not approved"):assemble(m,tmp_path/"out",p,d)

@pytest.mark.parametrize("target", ["https://example.com/image.png", "http://example.com/image.png", "mailto:image@example.com", "#image", "?image=1", ""])
def test_remote_images_are_rejected(tmp_path,target):
 m,p,d=fixture(tmp_path,ptext=f"# P\n\n![Remote]({target})\n")
 with pytest.raises(CollectionError,match="image is not approved"):assemble(m,tmp_path/"out",p,d)

def test_approved_image_is_relocated_and_copied(tmp_path):
 m,p,d=fixture(tmp_path);(p/"README.md").write_text("# P\n\n![Plot](plot.png)\n");image=b"\x89PNG\r\n\x1a\nfixture";(p/"plot.png").write_bytes(image);git(p,"add","README.md","plot.png");git(p,"commit","-qm","image content");content=git(p,"rev-parse","HEAD")
 contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["source_commit"]=content;contract["files"].append({"source":"plot.png","destination":"pydasc/assets/plot.png","media_type":"image/png","documentation_status":{"label":"Reviewed","evidence":"test"},"redistribution":{"spdx_license":"MIT","license_file":"LICENSE"}});contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","approve image")
 data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD");data["sources"]["pydasc"]["files"].append({"source":"plot.png","destination":"pydasc/assets/plot.png"});m.write_text(yaml.safe_dump(data));out=tmp_path/"out";assemble(m,out,p,d)
 assert "![Plot](assets/plot.png)" in (out/"pydasc/index.md").read_text();assert (out/"pydasc/assets/plot.png").read_bytes()==image

def test_dasc_attribution_is_preserved_in_output_and_inventory(tmp_path):
 m,p,d=fixture(tmp_path);out=tmp_path/"out";inventory=assemble(m,out,p,d);generated=(out/"dasc/index.md").read_text();dasc_item=next(item for item in inventory if item["destination"]=="dasc/index.md")
 assert dasc_item["attribution"]=="Test";assert "attribution=Test" in generated;assert "**Attribution:** Test" in generated;validate(m,out)

@pytest.mark.parametrize("payload", [
 "<svg><script>alert(1)</script></svg>",
 '<svg onload="alert(1)"></svg>',
 "<svg><foreignObject><div>active</div></foreignObject></svg>",
 '<svg><image href="https://example.invalid/tracker.png"/></svg>',
])
def test_svg_publication_is_rejected(tmp_path, payload):
 m,p,d=fixture(tmp_path);(p/"attack.svg").write_text(payload);git(p,"add","attack.svg");git(p,"commit","-qm","svg content");content=git(p,"rev-parse","HEAD")
 contract_path=p/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["source_commit"]=content;contract["files"].append({"source":"attack.svg","destination":"pydasc/assets/attack.svg","media_type":"image/svg+xml","documentation_status":{"label":"Reviewed","evidence":"test"},"redistribution":{"spdx_license":"MIT","license_file":"LICENSE"}});contract_path.write_text(json.dumps(contract));git(p,"add","docs/publication-manifest.json");git(p,"commit","-qm","approve svg")
 data=yaml.safe_load(m.read_text());data["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD");data["sources"]["pydasc"]["files"].append({"source":"attack.svg","destination":"pydasc/assets/attack.svg"});m.write_text(yaml.safe_dump(data))
 with pytest.raises(CollectionError,match="invalid approved file"):assemble(m,tmp_path/"out",p,d)

def test_inventory_must_match_manifest_selection_and_provenance(tmp_path):
 m,p,d=fixture(tmp_path);out=tmp_path/"out";assemble(m,out,p,d);inventory_path=out/"generated-inventory.json";inventory=json.loads(inventory_path.read_text())
 inventory["files"][0]["source"]="UNLISTED.md";inventory_path.write_text(json.dumps(inventory))
 with pytest.raises(CollectionError,match="provenance differs from manifest"):validate(m,out)
 assemble(m,out,p,d);inventory=json.loads(inventory_path.read_text());item=next(entry for entry in inventory["files"] if entry["destination"]=="pydasc/index.md");(out/"pydasc/index.md").rename(out/"pydasc/rogue.md");item["destination"]="pydasc/rogue.md";inventory_path.write_text(json.dumps(inventory))
 with pytest.raises(CollectionError,match="inventory differs from manifest"):validate(m,out)

@pytest.mark.parametrize("bad_item", [None, [], {}, {"destination":"pydasc/index.md"}])
def test_malformed_inventory_item_has_controlled_error(tmp_path, bad_item):
 m,p,d=fixture(tmp_path);out=tmp_path/"out";assemble(m,out,p,d);inventory_path=out/"generated-inventory.json";inventory=json.loads(inventory_path.read_text());inventory["files"][0]=bad_item;inventory_path.write_text(json.dumps(inventory))
 with pytest.raises(CollectionError,match="invalid inventory item"):validate(m,out)

def test_non_string_inventory_destination_has_controlled_error(tmp_path):
 m,p,d=fixture(tmp_path);out=tmp_path/"out";assemble(m,out,p,d);inventory_path=out/"generated-inventory.json";inventory=json.loads(inventory_path.read_text());inventory["files"][0]["destination"]=[];inventory_path.write_text(json.dumps(inventory))
 with pytest.raises(CollectionError,match="invalid inventory destination"):validate(m,out)

@pytest.mark.parametrize(("field", "value", "pattern"), [
 ("commit", "not-a-commit", "inventory commit"),
 ("status", "Unknown", "inventory status"),
 ("license", "MIT OR", "inventory license"),
 ("attribution", "<unsafe>", "inventory attribution"),
])
def test_inventory_provenance_fields_are_validated(tmp_path, field, value, pattern):
 m,p,d=fixture(tmp_path);out=tmp_path/"out";assemble(m,out,p,d);inventory_path=out/"generated-inventory.json";inventory=json.loads(inventory_path.read_text());inventory["files"][0][field]=value;inventory_path.write_text(json.dumps(inventory))
 with pytest.raises(CollectionError,match=pattern):validate(m,out)

def test_markdown_banner_must_match_inventory_provenance(tmp_path):
 m,p,d=fixture(tmp_path);out=tmp_path/"out";assemble(m,out,p,d);inventory_path=out/"generated-inventory.json";inventory=json.loads(inventory_path.read_text());inventory["files"][0]["commit"]="a"*40;inventory_path.write_text(json.dumps(inventory))
 with pytest.raises(CollectionError,match="unsafe/missing provenance"):validate(m,out)

def test_release_keeps_api_and_examples_static():
 root=Path(__file__).parents[1];data=yaml.safe_load((root/"docs-manifest.yml").read_text());selected=[entry["source"] for source in data["sources"].values() for entry in source["files"]]
 assert "docs/PUBLIC_API.md" in selected
 assert all(not path.casefold().endswith(".ipynb") for path in selected)
 assert all(not any(part.casefold() in {"examples","notebooks"} for part in Path(path).parts) for path in selected)
 requirements=(root/"requirements-docs.txt").read_text().casefold()
 assert all(tool not in requirements for tool in ("jupyter","nbconvert","mkdocstrings","pydoc"))

def test_markdown_policy_extensions_match_mkdocs_configuration():
 root=Path(__file__).parents[1];configured=yaml.safe_load((root/"mkdocs.yml").read_text())["markdown_extensions"]
 names=[entry if isinstance(entry,str) else next(iter(entry)) for entry in configured]
 assert names==MARKDOWN_POLICY_EXTENSIONS

def test_portal_enters_dasc_through_project_first_overview():
 root=Path(__file__).parents[1]
 assert "[Open the DASC documentation](dasc-project-overview.md)" in (root/"docs/index.md").read_text()
 assert "[DASC project overview](dasc-project-overview.md)" in (root/"docs/getting-started.md").read_text()

def test_attr_list_event_handler_on_a_link_is_rejected(tmp_path):
 m,p,d=fixture(tmp_path,ptext='# P\n\n[Link](https://example.com/){onclick="alert(1)"}\n')
 with pytest.raises(CollectionError,match="unsafe rendered attribute"):assemble(m,tmp_path/"out",p,d)

def test_attr_list_event_handler_on_image_is_rejected(tmp_path):
 m,p,d=fixture(tmp_path,ptext='# P\n\n![alt](https://example.com/x.png){onerror="alert(1)"}\n')
 with pytest.raises(CollectionError,match="unsafe rendered attribute"):assemble(m,tmp_path/"out",p,d)

def test_fence_glued_to_list_marker_does_not_hide_raw_script(tmp_path):
 m,p,d=fixture(tmp_path,ptext="# P\n\n- ~~~html\n  <script>alert(1)</script>\n  ~~~\n")
 with pytest.raises(CollectionError,match="active rendered HTML"):assemble(m,tmp_path/"out",p,d)

def test_indented_code_inside_blockquote_is_not_a_live_link(tmp_path):
 m,p,d=fixture(tmp_path,ptext="# P\n\n> quote\n>\n>     [literal](<guide file.md>)\n")
 assemble(m,tmp_path/"out",p,d)

def test_html_entity_in_destination_resolves_to_approved_file(tmp_path):
 m,p,d=fixture(tmp_path,ptext="# P\n\n[Home](README&#46;md)\n")
 out=tmp_path/"out";assemble(m,out,p,d);validate(m,out)
 assert "[Home](index.md)" in (out/"pydasc/index.md").read_text()


def test_duplicate_href_cannot_hide_unsafe_url_in_masked_html(tmp_path):
    text = (
        '# P\n\n<!-- [Example](https://example.com/) -->\n\n'
        '- ~~~html\n'
        '  <a href="javascript:alert(1)" HREF="https://example.com/">Link</a>\n'
        '  ~~~\n'
    )
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    with pytest.raises(CollectionError, match="duplicate HTML attribute: href"):
        assemble(manifest, tmp_path / "out", pydasc, dasc)


@pytest.mark.parametrize("html,pattern", [
    ('<a href="javascript:alert(1)">Link</a>', "unsafe link"),
    ('<a href="jav&#x61;script:alert(1)">Link</a>', "unsafe link"),
    ('<a href="java&#9;script:alert(1)">Link</a>', "unsafe rendered URL"),
    ('<img src="https://example.com/x.png">', "image is not approved"),
    ('<img src="data:text/html,active" src="approved.png">', "duplicate HTML attribute"),
])
def test_rendered_urls_are_checked_without_source_matches(html, pattern):
    from pathlib import PurePosixPath

    text = f"# P\n\n- ~~~html\n  {html}\n  ~~~\n"
    with pytest.raises(CollectionError, match=pattern):
        collect_docs._markdown_link_matches(text, PurePosixPath("README.md"))


@pytest.mark.parametrize("destination", [
    "https://example.com/a&#41;b",
    "https://example.com/a&#32;b?q=&quot;quoted&quot;&amp;x=1",
    "https://example.com/?q=&amp;copy;",
    "?q=&#41;&amp;x=&#32;#part",
    "#part&#41;with&#32;space",
])
def test_unchanged_urls_preserve_entities_and_rendered_destinations(tmp_path, destination):
    import markdown
    from html import unescape

    text = f"# P\n\n[Link]({destination})\n"
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    generated = (output / "pydasc/index.md").read_text()
    assert f"[Link]({destination})" in generated
    parser = collect_docs.RenderedReferenceParser()
    parser.feed(markdown.markdown(generated, extensions=MARKDOWN_POLICY_EXTENSIONS))
    assert ("link", unescape(destination)) in parser.references


def test_rewritten_query_and_fragment_are_safe_markdown(tmp_path):
    text = '# P\n\n[Home](README&#46;md?q=&#41;&amp;name=&#32;&amp;literal=%26copy%3B#part&#40;)\n'
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    generated = (output / "pydasc/index.md").read_text()
    assert "[Home](index.md?q=%29&amp;name=%20&amp;literal=%26copy%3B#part%28)" in generated


@pytest.mark.parametrize("literal", [
    "<!-- [Example](README.md) -->",
    "<!--\n~~~\n[Example](README.md)\n~~~\n-->",
    "`[Example](README.md)`",
    ">     [Example](README.md)",
    "<div>\n[Example](README.md)\n</div>",
])
def test_literal_link_occurrence_cannot_consume_visible_matches(tmp_path, literal):
    text = f"# P\n\n{literal}\n\n[Home](README.md)\n\n[Again](README.md)\n"
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    generated = (output / "pydasc/index.md").read_text()
    assert literal in generated
    assert "[Home](index.md)" in generated
    assert "[Again](index.md)" in generated
    assert "dasc-policy-" not in generated


def test_unsupported_link_examples_in_comments_are_ignored(tmp_path):
    text = '# P\n\n<!-- [Example](<guide file.md>) -->\n\n[Home](README.md)\n'
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    assert '<!-- [Example](<guide file.md>) -->' in (output / "pydasc/index.md").read_text()


def test_autolink_comment_cannot_hide_unsupported_raw_anchor():
    from pathlib import PurePosixPath

    text = (
        '# P\n\n<!-- <https://example.com/> -->\n\n'
        '- ~~~html\n  <a href="https://example.com/">Link</a>\n  ~~~\n'
    )
    with pytest.raises(CollectionError, match="unsupported rendered Markdown link syntax"):
        collect_docs._markdown_link_matches(text, PurePosixPath("README.md"))


@pytest.mark.parametrize("target", [
    "https://example.com/a)b", "user@example.com", "https://example.com/?a=1&b=2",
])
def test_autolink_occurrences_preserve_url_syntax(target):
    from pathlib import PurePosixPath

    text = f"<!-- <{target}> -->\n\n<{target}>\n"
    assert collect_docs._markdown_link_matches(text, PurePosixPath("README.md")) == []


def test_live_link_in_fence_like_list_is_rewritten(tmp_path):
    text = '# P\n\n> - ~~~markdown\n>   [Home](README.md)\n>   ~~~\n'
    manifest, pydasc, dasc = fixture(tmp_path, ptext=text)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    assert "[Home](index.md)" in (output / "pydasc/index.md").read_text()


@pytest.mark.parametrize("location", ["source", "inside", "ancestor", "alias", "alias_parent", "dotdot"])
def test_output_overlap_is_rejected_before_staging_or_source_inspection(tmp_path, monkeypatch, location):
    manifest, pydasc, dasc = fixture(tmp_path)
    before = (hashes(pydasc), hashes(dasc))
    heads = (git(pydasc, "rev-parse", "HEAD"), git(dasc, "rev-parse", "HEAD"))
    alias = tmp_path / "alias"
    alias.symlink_to(pydasc, target_is_directory=True)
    paths = {
        "source": pydasc,
        "inside": pydasc / "generated",
        "ancestor": tmp_path,
        "alias": alias,
        "alias_parent": alias / "generated",
        "dotdot": pydasc / "docs" / "..",
    }
    def unexpected_work(*args, **kwargs):
        pytest.fail("unsafe output must fail before source inspection or staging")
    monkeypatch.setattr(collect_docs, "_tree_state", unexpected_work)
    monkeypatch.setattr(collect_docs.tempfile, "TemporaryDirectory", unexpected_work)
    with pytest.raises(CollectionError, match="overlaps|unsafe output"):
        assemble(manifest, paths[location], pydasc, dasc)
    assert before == (hashes(pydasc), hashes(dasc))
    assert heads == (git(pydasc, "rev-parse", "HEAD"), git(dasc, "rev-parse", "HEAD"))


@pytest.mark.parametrize("location", [
    "pydasc", "dasc", "inside_existing", "inside_missing", "ancestor", "checkout_alias",
])
def test_case_alias_output_overlap_rejected_before_any_work(tmp_path, monkeypatch, location):
    manifest, pydasc, dasc = fixture(tmp_path)
    alias = pydasc.with_name("PYDASC")
    if not alias.exists() or not alias.samefile(pydasc):
        pytest.skip("requires a case-insensitive filesystem")
    (pydasc / "generated").mkdir()
    output = {
        "pydasc": alias,
        "dasc": dasc.with_name("DASC"),
        "inside_existing": alias / "generated",
        "inside_missing": alias / "not-created" / "nested",
        "ancestor": tmp_path.with_name(tmp_path.name.upper()),
        "checkout_alias": pydasc / "not-created" / "nested",
    }[location]
    before = (hashes(pydasc), hashes(dasc))
    heads = (git(pydasc, "rev-parse", "HEAD"), git(dasc, "rev-parse", "HEAD"))

    def unexpected_work(*args, **kwargs):
        pytest.fail("case aliases must fail before inspection, staging, or deletion")

    monkeypatch.setattr(collect_docs, "_tree_state", unexpected_work)
    monkeypatch.setattr(collect_docs.tempfile, "TemporaryDirectory", unexpected_work)
    monkeypatch.setattr(collect_docs.shutil, "rmtree", unexpected_work)
    with pytest.raises(CollectionError, match="overlaps"):
        assemble(manifest, output, alias if location == "checkout_alias" else pydasc, dasc)
    assert before == (hashes(pydasc), hashes(dasc))
    assert heads == (git(pydasc, "rev-parse", "HEAD"), git(dasc, "rev-parse", "HEAD"))
    assert not (pydasc / "not-created").exists()


@pytest.mark.parametrize("location", ["PYDASC/manifest.yml", "DASC/manifest.yml", "GENERATED-INVENTORY.JSON"])
def test_case_alias_output_cannot_replace_manifest(tmp_path, location):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    relocated = output / location
    relocated.parent.mkdir(parents=True)
    relocated.write_bytes(manifest.read_bytes())
    alias = output / location.lower()
    if not alias.exists() or not alias.samefile(relocated):
        pytest.skip("requires a case-insensitive filesystem")
    before = hashes(output)
    with pytest.raises(CollectionError, match="replace the input manifest"):
        assemble(relocated, output, pydasc, dasc)
    assert hashes(output) == before


def test_filesystem_containment_walks_existing_alias_ancestors(tmp_path):
    # Exercise identity comparisons on case-sensitive CI too; resolve() is
    # deliberately not used here because it would remove this test alias.
    root = tmp_path / "source"
    root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    assert collect_docs._filesystem_inside(alias, root)
    assert collect_docs._filesystem_inside(alias / "missing" / "nested", root)
    assert collect_docs._filesystem_inside(root / "missing" / "nested", alias)
    assert not collect_docs._filesystem_inside(tmp_path / "elsewhere", root)
    assert not collect_docs._filesystem_inside(root, tmp_path / "missing")


def test_filesystem_containment_does_not_fold_distinct_names(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    other = tmp_path / "SOURCE"
    if other.exists():
        pytest.skip("requires a case-sensitive filesystem")
    other.mkdir()
    assert not collect_docs._filesystem_inside(other / "missing", root)
    assert not collect_docs._filesystem_inside(root, other)


def test_output_identity_inspection_errors_fail_closed(tmp_path, monkeypatch):
    output = tmp_path / "out"
    checkout = tmp_path / "source"
    checkout.mkdir()
    original_stat = Path.stat

    def denied_stat(path, *args, **kwargs):
        if path == checkout:
            raise PermissionError("cannot inspect source identity")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", denied_stat)
    with pytest.raises(CollectionError, match="cannot inspect output paths"):
        collect_docs._preflight_output(output, {"pydasc": checkout}, tmp_path / "lock.yml")
    assert not output.exists()


@pytest.mark.parametrize("kind", ["symlink", "dangling", "directory", "fifo"])
def test_inventory_path_rejected_before_any_output_changes(tmp_path, kind):
    import os

    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    before = (hashes(pydasc), hashes(dasc), hashes(output / "pydasc"), hashes(output / "dasc"))
    external = tmp_path / "external.json"
    external.write_text("untouched")
    inventory = output / "generated-inventory.json"
    inventory.unlink()
    if kind == "symlink":
        inventory.symlink_to(external)
    elif kind == "dangling":
        inventory.symlink_to(tmp_path / "missing.json")
    elif kind == "directory":
        inventory.mkdir()
    else:
        os.mkfifo(inventory)
    with pytest.raises(CollectionError, match="unsafe inventory path"):
        assemble(manifest, output, pydasc, dasc)
    with pytest.raises(CollectionError, match="unsafe inventory path"):
        validate(manifest, output)
    assert before == (hashes(pydasc), hashes(dasc), hashes(output / "pydasc"), hashes(output / "dasc"))
    assert external.read_text() == "untouched"
    assert not (tmp_path / "missing.json").exists()
    assert not list(output.glob(".generated-inventory-*.tmp"))


@pytest.mark.parametrize("kind", ["symlink", "dangling", "file"])
def test_all_namespaces_are_checked_before_replacing_first_namespace(tmp_path, kind):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    (output / "pydasc").mkdir(parents=True)
    (output / "pydasc/keep.txt").write_text("old output")
    (output / "generated-inventory.json").write_text("old inventory")
    if kind == "file":
        (output / "dasc").write_text("not a directory")
    else:
        (output / "dasc").symlink_to(dasc if kind == "symlink" else tmp_path / "missing", target_is_directory=True)
    before = (hashes(pydasc), hashes(dasc))
    with pytest.raises(CollectionError, match="unsafe generated namespace"):
        assemble(manifest, output, pydasc, dasc)
    assert (output / "pydasc/keep.txt").read_text() == "old output"
    assert (output / "generated-inventory.json").read_text() == "old inventory"
    assert before == (hashes(pydasc), hashes(dasc))


@pytest.mark.parametrize("location", ["pydasc/manifest.yml", "dasc/manifest.yml", "generated-inventory.json"])
def test_publication_cannot_overwrite_its_input_manifest(tmp_path, location):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    relocated = output / location
    relocated.parent.mkdir(parents=True)
    relocated.write_bytes(manifest.read_bytes())
    before = relocated.read_bytes()
    with pytest.raises(CollectionError, match="replace the input manifest"):
        assemble(relocated, output, pydasc, dasc)
    assert relocated.read_bytes() == before


def test_inventory_replacement_does_not_modify_a_hardlink_target(tmp_path):
    import os

    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    output.mkdir()
    external = tmp_path / "external.json"
    external.write_text("untouched")
    inventory = output / "generated-inventory.json"
    os.link(external, inventory)
    assemble(manifest, output, pydasc, dasc)
    validate(manifest, output)
    assert external.read_text() == "untouched"
    assert not inventory.samefile(external)
    assert inventory.stat().st_mode & 0o777 == 0o644
    assert not list(output.glob(".generated-inventory-*.tmp"))


def test_failed_atomic_inventory_replace_preserves_previous_file(tmp_path, monkeypatch):
    inventory = tmp_path / "generated-inventory.json"
    inventory.write_text("old inventory")
    def fail_replace(source, destination):
        assert Path(source).parent == inventory.parent
        assert json.loads(Path(source).read_text()) == {"schema_version": 1, "files": []}
        assert Path(destination) == inventory
        raise OSError("simulated replace failure")
    monkeypatch.setattr(collect_docs.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        collect_docs._write_inventory_atomic(inventory, [])
    assert inventory.read_text() == "old inventory"
    assert not list(tmp_path.glob(".generated-inventory-*.tmp"))


def test_output_paths_are_rechecked_after_staging(tmp_path, monkeypatch):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    before = (hashes(output / "pydasc"), hashes(output / "dasc"))
    external = tmp_path / "external.json"
    external.write_text("untouched")
    original = collect_docs._rewrite
    def change_inventory_after_preflight(*args, **kwargs):
        inventory = output / "generated-inventory.json"
        if not inventory.is_symlink():
            inventory.unlink()
            inventory.symlink_to(external)
        return original(*args, **kwargs)
    monkeypatch.setattr(collect_docs, "_rewrite", change_inventory_after_preflight)
    with pytest.raises(CollectionError, match="unsafe inventory path"):
        assemble(manifest, output, pydasc, dasc)
    assert before == (hashes(output / "pydasc"), hashes(output / "dasc"))
    assert external.read_text() == "untouched"


@pytest.mark.parametrize("kind", ["file", "symlink", "dangling"])
def test_invalid_output_root_is_rejected_without_changes(tmp_path, kind):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    external = tmp_path / "external"
    external.mkdir()
    (external / "keep.txt").write_text("untouched")
    if kind == "file":
        output.write_text("untouched")
    else:
        output.symlink_to(external if kind == "symlink" else tmp_path / "missing", target_is_directory=True)
    before = (hashes(pydasc), hashes(dasc), hashes(external))
    with pytest.raises(CollectionError, match="unsafe output directory"):
        assemble(manifest, output, pydasc, dasc)
    assert before == (hashes(pydasc), hashes(dasc), hashes(external))
    assert not (tmp_path / "missing").exists()


def test_manifest_symlink_inside_output_namespace_is_preserved(tmp_path):
    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    (output / "pydasc").mkdir(parents=True)
    alias = output / "pydasc/manifest.yml"
    alias.symlink_to(manifest)
    with pytest.raises(CollectionError, match="replace the input manifest"):
        assemble(alias, output, pydasc, dasc)
    assert alias.is_symlink()
    assert alias.read_bytes() == manifest.read_bytes()
    parent_alias = tmp_path / "output-alias"
    parent_alias.symlink_to(output, target_is_directory=True)
    with pytest.raises(CollectionError, match="replace the input manifest"):
        assemble(parent_alias / "pydasc/manifest.yml", output, pydasc, dasc)
    assert alias.is_symlink()


@pytest.mark.parametrize("kind", ["symlink", "fifo"])
def test_validation_rejects_inventory_replaced_after_path_check(tmp_path, monkeypatch, kind):
    import os
    import validate_docs

    manifest, pydasc, dasc = fixture(tmp_path)
    output = tmp_path / "out"
    assemble(manifest, output, pydasc, dasc)
    inventory = output / "generated-inventory.json"
    external = tmp_path / "external.json"
    external.write_bytes(inventory.read_bytes())
    original = validate_docs._check_inventory_path
    def change_entry(path, **kwargs):
        original(path, **kwargs)
        inventory.unlink()
        if kind == "symlink":
            inventory.symlink_to(external)
        else:
            os.mkfifo(inventory)
    monkeypatch.setattr(validate_docs, "_check_inventory_path", change_entry)
    with pytest.raises(CollectionError, match="invalid inventory|unsafe inventory"):
        validate(manifest, output)


def test_atomic_writer_rechecks_inventory_before_replacement(tmp_path, monkeypatch):
    inventory = tmp_path / "generated-inventory.json"
    inventory.write_text("previous")
    external = tmp_path / "external.json"
    external.write_text("untouched")
    def swap_during_write(fd):
        inventory.unlink()
        inventory.symlink_to(external)
    monkeypatch.setattr(collect_docs.os, "fsync", swap_during_write)
    with pytest.raises(CollectionError, match="unsafe inventory path"):
        collect_docs._write_inventory_atomic(inventory, [])
    assert external.read_text() == "untouched"
    assert not list(tmp_path.glob(".generated-inventory-*.tmp"))


def test_publication_output_characterization(tmp_path):
    """Independently specify approved bytes and provenance, not generator internals."""
    manifest, pydasc, dasc = fixture(tmp_path, ptext="# P\n[License](LICENSE)\n")
    output = tmp_path / "published"
    inventory = assemble(manifest, output, pydasc, dasc)
    for item in inventory:
        project = "PyDASC" if item["destination"].startswith("pydasc/") else "DASC"
        attribution = "" if project == "PyDASC" else "Test"
        url = f"{item['repository']}/blob/{item['commit']}/README.md"
        expected = (
            f"<!-- Generated; source={url}; status=Reviewed; license=MIT; attribution={attribution}; do not edit. -->\n\n"
            '!!! info "Publication record"\n'
            f"    **Project:** {project} · **Status:** Reviewed · **License:** `MIT`  \n"
            + (f"    **Attribution:** {attribution}  \n" if attribution else "")
            + f"    **Immutable revision:** [`{item['commit']}`]({url}) · **Source path:** `README.md`\n\n"
        )
        expected += (
            f"# P\n[License]({item['repository']}/blob/{item['commit']}/LICENSE)\n"
            if project == "PyDASC" else "# D\n"
        )
        assert (output / item["destination"]).read_bytes() == expected.encode()
        assert item == {
            "destination": "pydasc/index.md" if project == "PyDASC" else "dasc/index.md",
            "sha256": hashlib.sha256(expected.encode()).hexdigest(),
            "repository": f"https://github.com/pydasc/{'pydasc' if project == 'PyDASC' else 'dasc'}",
            "source": "README.md", "commit": item["commit"], "status": "Reviewed",
            "license": "MIT", "attribution": attribution,
        }
    validate(manifest, output)
