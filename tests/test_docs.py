from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path
import pytest, yaml
sys.path.insert(0,str(Path(__file__).parents[1]/"scripts"))
import collect_docs
from collect_docs import CollectionError, assemble, load_manifest
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
 text="# P\n\n```markdown\n[guide]: missing.md\n```\n\n    [other]: missing.md\n"
 m,p,d=fixture(tmp_path,ptext=text);out=tmp_path/"out";assemble(m,out,p,d);validate(m,out)

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
 m,p,d=fixture(tmp_path);monkeypatch.setattr(collect_docs,"MAX_FILE_BYTES",1)
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

def test_portal_enters_dasc_through_project_first_overview():
 root=Path(__file__).parents[1]
 assert "[Open the DASC documentation](dasc-project-overview.md)" in (root/"docs/index.md").read_text()
 assert "[DASC project overview](dasc-project-overview.md)" in (root/"docs/getting-started.md").read_text()
