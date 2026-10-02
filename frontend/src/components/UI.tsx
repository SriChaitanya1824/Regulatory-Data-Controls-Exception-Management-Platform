import {ReactNode} from 'react';
export const Badge=({children}:{children:ReactNode})=><span className={`badge b-${String(children).toLowerCase().replaceAll(' ','-')}`}>{children}</span>;
export const Panel=({title,sub,action,children}:{title:string;sub?:string;action?:ReactNode;children:ReactNode})=><section className="panel"><div className="panel-head"><div><h2>{title}</h2>{sub&&<p>{sub}</p>}</div>{action}</div>{children}</section>;
export const Loading=()=> <div className="loading">Loading governance records…</div>;
