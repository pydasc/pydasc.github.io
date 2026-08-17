from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path
import pytest, yaml
sys.path.insert(0,str(Path(__file__).parents[1]/"scripts"))
from collect_docs import CollectionError, assemble, load_manifest
from validate_docs import validate
from update_source_locks import main as update_source_locks_main
from update_source_locks import update as update_source_locks

def git(repo:Path,*args:str)->str:return subprocess.run(["git",*args],cwd=repo,check=True,capture_output=True,text=True).stdout.strip()
def repo(root:Path,name:str,text:str)->tuple[Path,str]:
 r=root/name;r.mkdir();git(r,"init","-q");git(r,"config","user.email","t@invalid");git(r,"config","user.name","T");(r/"README.md").write_text(text);(r/"LICENSE").write_text("MIT License\n");git(r,"add",".");git(r,"commit","-qm","content");content=git(r,"rev-parse","HEAD")
 rights={"spdx_license":"MIT","license_file":"LICENSE"};
 if name=="dasc":rights["attribution"]="Test"
 contract={"schema_version":1,"project":name,"repository":f"https://github.com/chongshikpark/{name}","source_commit":content,"files":[{"source":"README.md","destination":f"{name}/index.md","media_type":"text/markdown","documentation_status":{"label":"Reviewed","evidence":"test"},"redistribution":rights}]}
 if name=="dasc":contract["publication_decision"]={"state":"approved","reason":"test","evidence":"test"}
 (r/"docs").mkdir();(r/"docs/publication-manifest.json").write_text(json.dumps(contract));git(r,"add",".");git(r,"commit","-qm","contract");return r,git(r,"rev-parse","HEAD")
def fixture(tmp:Path,ptext="# P\n",dtext="# D\n"):
 p,pc=repo(tmp,"pydasc",ptext);d,dc=repo(tmp,"dasc",dtext);data={"schema_version":2,"sources":{n:{"repository":f"https://github.com/chongshikpark/{n}","checkout_commit":c,"publication_manifest":"docs/publication-manifest.json","files":[{"source":"README.md","destination":f"{n}/index.md"}]} for n,c in (("pydasc",pc),("dasc",dc))}};m=tmp/"lock.yml";m.write_text(yaml.safe_dump(data));return m,p,d
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

def test_source_lock_update_validates_candidate_and_changes_only_commit(tmp_path):
 m,p,d=fixture(tmp_path);before=yaml.safe_load(m.read_text());(p/"CHANGELOG.md").write_text("candidate\n");git(p,"add","CHANGELOG.md");git(p,"commit","-qm","candidate")
 changes=update_source_locks(m,{"pydasc":p,"dasc":d});after=yaml.safe_load(m.read_text())
 assert changes=={"pydasc":(before["sources"]["pydasc"]["checkout_commit"],git(p,"rev-parse","HEAD"))}
 assert after["sources"]["pydasc"]["checkout_commit"]==git(p,"rev-parse","HEAD")
 before["sources"]["pydasc"]["checkout_commit"]=git(p,"rev-parse","HEAD")
 assert after==before

def test_source_lock_cli_skips_unapproved_candidate_without_changes(tmp_path,capsys):
 m,p,d=fixture(tmp_path);before=m.read_bytes();contract_path=d/"docs/publication-manifest.json";contract=json.loads(contract_path.read_text());contract["publication_decision"]["state"]="draft";contract_path.write_text(json.dumps(contract));git(d,"add",str(contract_path.relative_to(d)));git(d,"commit","-qm","draft contract")
 rejected=update_source_locks_main(["--manifest",str(m),"--pydasc",str(p),"--dasc",str(d)])
 assert rejected==1;assert m.read_bytes()==before;assert "error: DASC publication decision is not approved" in capsys.readouterr().err
 result=update_source_locks_main(["--skip-unapproved","--manifest",str(m),"--pydasc",str(p),"--dasc",str(d)])
 assert result==0;assert m.read_bytes()==before;assert "skip: DASC publication decision is not approved" in capsys.readouterr().out
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
def test_unknown_output_and_checksum_rejected(tmp_path):
 m,p,d=fixture(tmp_path);out=tmp_path/"out";assemble(m,out,p,d);(out/"dasc/extra.md").write_text("x")
 with pytest.raises(CollectionError,match="boundary"):validate(m,out)

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
